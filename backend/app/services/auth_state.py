from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import HTTPException, UploadFile

from app.core.config import settings

MAX_AUTH_STATE_BYTES = 5 * 1024 * 1024


def auth_state_status(platform: str) -> dict[str, Any]:
    path = settings.platform_auth_state_path(platform)
    if not path.exists():
        return {
            "platform": platform,
            "exists": False,
            "filename": path.name,
            "size_bytes": None,
            "updated_at": None,
            "cookie_count": 0,
            "has_required_cookie": False,
            "message": "登录态文件不存在",
        }

    try:
        state = _load_storage_state(path)
        stat = path.stat()
    except Exception as exc:
        return {
            "platform": platform,
            "exists": True,
            "filename": path.name,
            "size_bytes": path.stat().st_size if path.exists() else None,
            "updated_at": _mtime(path) if path.exists() else None,
            "cookie_count": 0,
            "has_required_cookie": False,
            "message": f"登录态文件无法解析：{exc}",
        }

    cookies = _cookies_from_state(state)
    has_required_cookie = _has_required_cookie(platform, cookies)
    message = "登录态文件已就绪" if has_required_cookie else "登录态文件存在，但缺少平台关键 cookie"
    return {
        "platform": platform,
        "exists": True,
        "filename": path.name,
        "size_bytes": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc),
        "cookie_count": len(cookies),
        "has_required_cookie": has_required_cookie,
        "message": message,
    }


async def save_uploaded_auth_state(platform: str, upload: UploadFile) -> dict[str, Any]:
    raw = await upload.read(MAX_AUTH_STATE_BYTES + 1)
    if len(raw) > MAX_AUTH_STATE_BYTES:
        raise HTTPException(status_code=413, detail="登录态文件过大，最大支持 5MB")

    try:
        text = raw.decode("utf-8")
        state = json.loads(text)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="登录态文件必须是 UTF-8 JSON") from None
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"登录态 JSON 格式错误：{exc.msg}") from None

    _validate_storage_state(state)
    cookies = _cookies_from_state(state)
    if not _has_required_cookie(platform, cookies):
        raise HTTPException(status_code=400, detail="登录态文件缺少平台关键 cookie，请确认上传的是 Playwright storage_state JSON")

    path = settings.platform_auth_state_path(platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = json.dumps(state, ensure_ascii=False, indent=2)
    with NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as temp_file:
        temp_file.write(normalized)
        temp_name = temp_file.name
    os.replace(temp_name, path)
    return auth_state_status(platform)


def delete_auth_state(platform: str) -> None:
    path = settings.platform_auth_state_path(platform)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _load_storage_state(path: Path) -> dict[str, Any]:
    state = json.loads(path.read_text(encoding="utf-8"))
    _validate_storage_state(state)
    return state


def _validate_storage_state(state: Any) -> None:
    if not isinstance(state, dict):
        raise ValueError("storage state must be a JSON object")
    cookies = state.get("cookies")
    origins = state.get("origins", [])
    if not isinstance(cookies, list):
        raise ValueError("storage state cookies must be a list")
    if not isinstance(origins, list):
        raise ValueError("storage state origins must be a list")


def _cookies_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [cookie for cookie in state.get("cookies", []) if isinstance(cookie, dict)]


def _has_required_cookie(platform: str, cookies: list[dict[str, Any]]) -> bool:
    if platform == "weibo":
        return any(cookie.get("domain", "").endswith("weibo.com") and cookie.get("name") == "SUB" for cookie in cookies)
    if platform == "xueqiu":
        return any(cookie.get("domain", "").endswith("xueqiu.com") for cookie in cookies)
    return bool(cookies)


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
