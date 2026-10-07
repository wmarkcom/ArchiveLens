from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.models import PlatformAccount, PlatformConnection
from app.services import session_health


def test_refresh_xueqiu_uses_timeline_login_check(monkeypatch) -> None:
    account = PlatformAccount(
        id=4,
        platform="xueqiu",
        account_name="浮光",
        profile_url="https://xueqiu.com/u/4531798617",
        platform_account_id="4531798617",
        is_enabled=True,
    )
    connection = PlatformConnection(
        id=1,
        platform="xueqiu",
        status="connected",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    connection_query = MagicMock()
    connection_query.filter.return_value.first.return_value = connection
    account_query = MagicMock()
    account_query.filter.return_value.order_by.return_value.first.return_value = account

    db = MagicMock()
    db.query.side_effect = [connection_query, account_query]

    adapter = MagicMock()
    adapter.check_login = AsyncMock(return_value=False)

    monkeypatch.setattr(session_health, "get_platform_adapter", lambda *args, **kwargs: adapter)
    monkeypatch.setattr(session_health, "_lock_connection", lambda db, platform, fallback: fallback)
    monkeypatch.setattr(session_health, "auth_state_status", lambda platform: {
        "platform": platform,
        "exists": True,
        "filename": "xueqiu.json",
        "size_bytes": 100,
        "updated_at": datetime.now(timezone.utc),
        "cookie_count": 10,
        "has_required_cookie": True,
        "message": "登录态文件已就绪",
    })
    monkeypatch.setattr(session_health.settings, "platform_auth_state_path", lambda platform: Path("xueqiu.json"))

    result = session_health.check_platform_session(
        db,
        "xueqiu",
        notify=False,
        trigger_scan=False,
    )

    adapter.check_login.assert_awaited_once_with("4531798617")
    assert result["status"] == "expired"
    assert connection.status == "expired"
    assert connection.error_message == "雪球时间线接口验证失败，登录态可能已失效，请重新登录或上传 xueqiu.json"
