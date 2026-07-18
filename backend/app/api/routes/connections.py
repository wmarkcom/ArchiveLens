from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_admin_token
from app.db.session import get_db
from app.models import PlatformConnection, PlatformLoginSession
from app.schemas.common import SuccessResponse
from app.schemas.connections import LoginSession, PlatformAuthStateOut, PlatformConnectionOut
from app.services.auth_state import auth_state_status, delete_auth_state, save_uploaded_auth_state
from app.services.browser_login import (
    click_browser_login_action,
    login_screenshot_path,
    login_session_payload,
    refresh_browser_login,
    start_browser_login,
)
from app.services.monitor_trigger import enqueue_monitor_scan
from app.services.platform.registry import get_platform_adapter

router = APIRouter(dependencies=[Depends(require_admin_token)])

PLATFORMS = ["weibo", "xueqiu"]


def _get_or_create_connection(db: Session, platform: str) -> PlatformConnection:
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")
    conn = db.query(PlatformConnection).filter(PlatformConnection.platform == platform).first()
    if conn is None:
        conn = PlatformConnection(platform=platform)
        db.add(conn)
        db.commit()
        db.refresh(conn)
    return conn


def _connection_out(conn: PlatformConnection) -> PlatformConnectionOut:
    return PlatformConnectionOut.model_validate(conn).model_copy(
        update={"auth_state": PlatformAuthStateOut.model_validate(auth_state_status(conn.platform))}
    )


@router.get("", response_model=dict)
def list_connections(db: Session = Depends(get_db)) -> dict:
    for platform in PLATFORMS:
        _get_or_create_connection(db, platform)
    rows = db.query(PlatformConnection).order_by(PlatformConnection.platform).all()
    items = [_connection_out(row) for row in rows]
    return {"items": items}


@router.get("/{platform}/status", response_model=PlatformConnectionOut)
def get_connection_status(platform: str, db: Session = Depends(get_db)) -> PlatformConnectionOut:
    conn = _get_or_create_connection(db, platform)
    return _connection_out(conn)


@router.post("/{platform}/login", response_model=LoginSession)
async def create_platform_login(platform: str, db: Session = Depends(get_db)) -> dict:
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")
    if platform != "weibo":
        raise HTTPException(status_code=400, detail="暂只支持微博扫码登录，雪球后续接入")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    session = PlatformLoginSession(platform=platform, status="pending", expires_at=expires_at)
    db.add(session)
    db.commit()
    db.refresh(session)

    conn = _get_or_create_connection(db, platform)
    conn.status = "pending_login"
    conn.error_message = None
    db.commit()

    try:
        await start_browser_login(db, session)
        db.refresh(session)
    except Exception as exc:
        session.status = "failed"
        session.error_message = str(exc)[:500]
        session.finished_at = datetime.now(timezone.utc)
        conn.status = "failed"
        conn.error_message = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=500, detail=f"启动扫码登录失败：{exc}") from exc
    return login_session_payload(session)


@router.get("/{platform}/login/{session_id}", response_model=LoginSession)
async def get_platform_login(platform: str, session_id: str, db: Session = Depends(get_db)) -> dict:
    session = (
        db.query(PlatformLoginSession)
        .filter(PlatformLoginSession.platform == platform, PlatformLoginSession.id == session_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="登录会话不存在")
    session = await refresh_browser_login(db, session)
    db.refresh(session)
    return login_session_payload(session)


@router.post("/{platform}/login/{session_id}/action", response_model=LoginSession)
async def run_platform_login_action(
    platform: str,
    session_id: str,
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    session = (
        db.query(PlatformLoginSession)
        .filter(PlatformLoginSession.platform == platform, PlatformLoginSession.id == session_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="登录会话不存在")
    session = await click_browser_login_action(db, session, payload)
    db.refresh(session)
    return login_session_payload(session)


@router.get("/{platform}/login/{session_id}/screenshot")
def get_platform_login_screenshot(platform: str, session_id: str, db: Session = Depends(get_db)) -> FileResponse:
    session = (
        db.query(PlatformLoginSession)
        .filter(PlatformLoginSession.platform == platform, PlatformLoginSession.id == session_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="登录会话不存在")
    try:
        path = login_screenshot_path(platform, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="登录截图尚未生成")
    return FileResponse(path, media_type="image/png")


@router.post("/{platform}/logout", response_model=SuccessResponse)
def logout_platform(platform: str, db: Session = Depends(get_db)) -> SuccessResponse:
    conn = _get_or_create_connection(db, platform)
    conn.status = "disconnected"
    conn.session_data_encrypted = None
    delete_auth_state(platform)
    db.commit()
    return SuccessResponse(message=f"{platform} 已解绑")


@router.get("/{platform}/auth-state", response_model=PlatformAuthStateOut)
def get_auth_state(platform: str, db: Session = Depends(get_db)) -> PlatformAuthStateOut:
    _get_or_create_connection(db, platform)
    return PlatformAuthStateOut.model_validate(auth_state_status(platform))


@router.post("/{platform}/auth-state", response_model=PlatformConnectionOut)
async def upload_auth_state(
    platform: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> PlatformConnectionOut:
    conn = _get_or_create_connection(db, platform)
    status = await save_uploaded_auth_state(platform, file)
    conn.session_data_encrypted = status["filename"]
    conn.status = "pending_login"
    conn.error_message = None
    db.commit()
    db.refresh(conn)
    return _connection_out(conn)


@router.post("/{platform}/refresh", response_model=PlatformConnectionOut)
def refresh_connection(platform: str, db: Session = Depends(get_db)) -> PlatformConnectionOut:
    """Refresh connection status by checking login validity via platform adapter."""
    conn = _get_or_create_connection(db, platform)

    storage_path = settings.platform_auth_state_path(platform)
    state_status = auth_state_status(platform)

    try:
        if not state_status["exists"]:
            is_valid = False
            error_message = "登录态文件不存在"
        elif not state_status["has_required_cookie"]:
            is_valid = False
            error_message = state_status["message"] or "登录态文件缺少平台关键 cookie"
        elif platform == "xueqiu":
            is_valid = True
            error_message = None
        else:
            adapter = get_platform_adapter(platform, storage_state_path=storage_path)
            is_valid = asyncio.run(adapter.check_login())
            error_message = None

        if is_valid:
            conn.status = "connected"
            conn.last_login_at = conn.last_login_at or datetime.now(timezone.utc)
            conn.session_data_encrypted = storage_path.name
            conn.error_message = None
        else:
            conn.status = "expired"
            conn.error_message = error_message or "Login check failed — session may be invalid or expired"
    except Exception as exc:
        conn.status = "failed"
        conn.error_message = str(exc)[:500]

    db.commit()
    db.refresh(conn)
    if conn.status == "connected":
        enqueue_monitor_scan()
    return _connection_out(conn)
