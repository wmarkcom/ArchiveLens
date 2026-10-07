from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PlatformAccount, PlatformConnection
from app.services.auth_state import auth_state_status
from app.services.monitor_trigger import enqueue_monitor_scan
from app.services.notifier import NotifierService
from app.services.platform.base import PlatformAuthenticationError
from app.services.platform.registry import get_platform_adapter, resolve_platform_account_id

logger = logging.getLogger(__name__)

PLATFORMS = ("weibo", "xueqiu")
PLATFORM_LABELS = {"weibo": "微博", "xueqiu": "雪球"}


def check_platform_session(
    db: Session,
    platform: str,
    *,
    notify: bool = True,
    trigger_scan: bool = True,
    failure_threshold: int | None = None,
) -> dict[str, Any]:
    if platform not in PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}")

    connection = _get_or_create_connection(db, platform)
    checked_at = datetime.now(timezone.utc)
    state_status = auth_state_status(platform)
    meta = dict(connection.session_meta or {})
    meta["last_checked_at"] = checked_at.isoformat()
    meta["cookie_updated_at"] = _isoformat(state_status.get("updated_at"))

    if not state_status["exists"]:
        return mark_platform_auth_expired(
            db,
            platform,
            "登录态文件不存在",
            connection=connection,
            checked_at=checked_at,
            session_meta=meta,
            notify=notify,
        )
    if not state_status["has_required_cookie"]:
        return mark_platform_auth_expired(
            db,
            platform,
            state_status["message"] or "登录态文件缺少平台关键 cookie",
            connection=connection,
            checked_at=checked_at,
            session_meta=meta,
            notify=notify,
        )

    account = _first_enabled_account(db, platform)
    account_id = (
        resolve_platform_account_id(platform, account.platform_account_id, account.profile_url)
        if account is not None
        else None
    )
    if account_id is None:
        return mark_platform_auth_expired(
            db,
            platform,
            "没有可用于检测的已启用博主",
            connection=connection,
            checked_at=checked_at,
            session_meta=meta,
            notify=notify,
        )

    try:
        adapter = get_platform_adapter(
            platform,
            storage_state_path=settings.platform_auth_state_path(platform),
        )
        is_valid = asyncio.run(adapter.check_login(account_id))
    except PlatformAuthenticationError as exc:
        return mark_platform_auth_expired(
            db,
            platform,
            str(exc),
            connection=connection,
            checked_at=checked_at,
            session_meta=meta,
            notify=notify,
        )
    except Exception as exc:
        return _mark_transient_failure(
            db,
            connection,
            exc,
            checked_at=checked_at,
            session_meta=meta,
            notify=notify,
            failure_threshold=failure_threshold,
        )

    if not is_valid:
        error_message = "Login check failed — session may be invalid or expired"
        if platform == "xueqiu":
            error_message = "雪球时间线接口验证失败，登录态可能已失效，请重新登录或上传 xueqiu.json"
        return mark_platform_auth_expired(
            db,
            platform,
            error_message,
            connection=connection,
            checked_at=checked_at,
            session_meta=meta,
            notify=notify,
        )

    connection = _lock_connection(db, platform, connection)
    previous_status = connection.status
    current_meta = dict(connection.session_meta or {})
    current_meta.update(meta)
    meta = current_meta
    refreshed_state = auth_state_status(platform)
    pending_from_status = meta.pop("status_before_login", None)
    meta.update(
        {
            "last_success_at": checked_at.isoformat(),
            "cookie_updated_at": _isoformat(refreshed_state.get("updated_at")),
            "consecutive_failures": 0,
            "last_error": None,
            "last_failure_kind": None,
        }
    )
    connection.status = "connected"
    connection.session_data_encrypted = refreshed_state["filename"]
    connection.last_login_at = connection.last_login_at or checked_at
    connection.expired_at = None
    connection.error_message = None
    connection.session_meta = meta
    db.commit()

    recovered = previous_status in {"expired", "failed"} or pending_from_status in {"expired", "failed"}
    if recovered and notify:
        _send_transition_notification(
            db,
            event_type="system",
            platform=platform,
            title=f"{PLATFORM_LABELS[platform]}登录已恢复",
            body=f"{PLATFORM_LABELS[platform]}登录态已通过真实接口验证，自动采集已恢复。",
            payload={
                "previous_status": pending_from_status or previous_status,
                "current_status": "connected",
            },
        )
    if trigger_scan and previous_status != "connected":
        enqueue_monitor_scan()

    return {
        "platform": platform,
        "status": "valid",
        "connection_status": connection.status,
        "recovered": recovered,
        "checked_at": checked_at.isoformat(),
        "consecutive_failures": 0,
    }


def mark_platform_auth_expired(
    db: Session,
    platform: str,
    error_message: str,
    *,
    connection: PlatformConnection | None = None,
    checked_at: datetime | None = None,
    session_meta: dict[str, Any] | None = None,
    notify: bool = True,
) -> dict[str, Any]:
    checked_at = checked_at or datetime.now(timezone.utc)
    connection = connection or _get_or_create_connection(db, platform)
    connection = _lock_connection(db, platform, connection)
    previous_status = connection.status
    meta = _merge_check_metadata(connection.session_meta, session_meta)
    consecutive_failures = int((connection.session_meta or {}).get("consecutive_failures") or 0) + 1
    meta.update(
        {
            "last_checked_at": checked_at.isoformat(),
            "consecutive_failures": consecutive_failures,
            "last_error": error_message[:500],
            "last_failure_kind": "authentication",
        }
    )
    connection.status = "expired"
    connection.expired_at = connection.expired_at or checked_at
    connection.error_message = error_message[:500]
    connection.session_meta = meta
    db.commit()

    transitioned = previous_status != "expired"
    notification_source = meta.get("status_before_login") or previous_status
    if transitioned and notification_source in {"connected", "failed"} and notify:
        _send_transition_notification(
            db,
            event_type="login_expired",
            platform=platform,
            title=f"{PLATFORM_LABELS.get(platform, platform)}登录态已失效",
            body=f"错误：{error_message[:500]}\n请重新登录或上传新的登录态 JSON。",
            payload={"previous_status": notification_source, "current_status": "expired"},
        )
    return {
        "platform": platform,
        "status": "expired",
        "connection_status": connection.status,
        "transitioned": transitioned,
        "checked_at": checked_at.isoformat(),
        "consecutive_failures": consecutive_failures,
        "error": error_message[:500],
    }


def _mark_transient_failure(
    db: Session,
    connection: PlatformConnection,
    error: Exception,
    *,
    checked_at: datetime,
    session_meta: dict[str, Any],
    notify: bool,
    failure_threshold: int | None,
) -> dict[str, Any]:
    connection = _lock_connection(db, connection.platform, connection)
    previous_status = connection.status
    current_meta = dict(connection.session_meta or {})
    session_meta = _merge_check_metadata(current_meta, session_meta)
    threshold = max(failure_threshold or settings.platform_session_failure_threshold, 1)
    message = str(error)[:500]
    consecutive_failures = int(current_meta.get("consecutive_failures") or 0) + 1
    session_meta.update(
        {
            "last_checked_at": checked_at.isoformat(),
            "consecutive_failures": consecutive_failures,
            "last_error": message,
            "last_failure_kind": "transient",
        }
    )
    connection.session_meta = session_meta
    became_failed = consecutive_failures >= threshold and previous_status != "failed"
    if consecutive_failures >= threshold:
        connection.status = "failed"
        connection.error_message = f"登录检测连续失败 {consecutive_failures} 次：{message}"
    db.commit()

    if became_failed and notify:
        _send_transition_notification(
            db,
            event_type="system",
            platform=connection.platform,
            title=f"{PLATFORM_LABELS.get(connection.platform, connection.platform)}登录检测连续失败",
            body=f"连续失败 {consecutive_failures} 次，暂未判定 Cookie 失效。\n最近错误：{message}",
            payload={"previous_status": previous_status, "current_status": connection.status},
        )
    return {
        "platform": connection.platform,
        "status": "transient_error",
        "connection_status": connection.status,
        "checked_at": checked_at.isoformat(),
        "consecutive_failures": consecutive_failures,
        "error": message,
    }


def _get_or_create_connection(db: Session, platform: str) -> PlatformConnection:
    connection = db.query(PlatformConnection).filter(PlatformConnection.platform == platform).first()
    if connection is None:
        connection = PlatformConnection(platform=platform)
        db.add(connection)
        db.commit()
        db.refresh(connection)
    return connection


def _first_enabled_account(db: Session, platform: str) -> PlatformAccount | None:
    return (
        db.query(PlatformAccount)
        .filter(PlatformAccount.platform == platform, PlatformAccount.is_enabled.is_(True))
        .order_by(PlatformAccount.id.asc())
        .first()
    )


def _lock_connection(
    db: Session,
    platform: str,
    fallback: PlatformConnection,
) -> PlatformConnection:
    locked = (
        db.query(PlatformConnection)
        .filter(PlatformConnection.platform == platform)
        .with_for_update()
        .first()
    )
    return locked or fallback


def _merge_check_metadata(
    current: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(current or {})
    for key in ("last_checked_at", "cookie_updated_at"):
        if incoming and key in incoming:
            merged[key] = incoming[key]
    return merged


def _send_transition_notification(
    db: Session,
    *,
    event_type: str,
    platform: str,
    title: str,
    body: str,
    payload: dict[str, Any],
) -> None:
    try:
        notifier = NotifierService(db)
        if not notifier.is_configured():
            return
        notifier.send_event(
            event_type=event_type,
            platform=platform,
            title=title,
            body=body,
            reference_id=platform,
            reference_type="platform_connection",
            payload=payload,
        )
    except Exception:
        logger.exception("Failed to send platform session transition notification for %s", platform)


def _isoformat(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
