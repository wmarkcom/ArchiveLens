from pathlib import Path

from app.core.config import settings
from app.services.platform.base import PlatformAdapter
from app.services.platform.mock import MockPlatformAdapter
from app.services.platform.weibo import WeiboAdapter, extract_weibo_uid
from app.services.platform.xueqiu import XueqiuAdapter, extract_xueqiu_uid


def get_platform_adapter(platform: str, *, storage_state_path: str | Path | None = None) -> PlatformAdapter:
    if platform == "weibo":
        if storage_state_path is None:
            raise ValueError("storage_state_path is required for weibo adapter")
        return WeiboAdapter(
            storage_state_path=storage_state_path,
            detail_timeout_ms=settings.weibo_detail_timeout_ms,
            list_timeout_ms=settings.weibo_list_timeout_ms,
        )
    if platform == "xueqiu":
        if storage_state_path is None:
            raise ValueError("storage_state_path is required for xueqiu adapter")
        return XueqiuAdapter(storage_state_path=storage_state_path)
    if platform == "mock":
        return MockPlatformAdapter()
    raise ValueError(f"Unsupported platform: {platform}")


def resolve_platform_account_id(platform: str, platform_account_id: str | None, profile_url: str) -> str:
    if platform == "weibo":
        uid = platform_account_id or extract_weibo_uid(profile_url)
        if uid is None:
            raise ValueError("Unable to resolve weibo uid from platform_account_id or profile_url")
        return uid
    if platform == "xueqiu":
        uid = platform_account_id or extract_xueqiu_uid(profile_url)
        if uid is None:
            raise ValueError("Unable to resolve xueqiu uid from platform_account_id or profile_url")
        return uid
    return platform_account_id or profile_url
