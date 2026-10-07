from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.models import PlatformConnection
from app.services import session_health


def _valid_auth_state(platform: str) -> dict:
    return {
        "platform": platform,
        "exists": True,
        "filename": f"{platform}.json",
        "size_bytes": 100,
        "updated_at": datetime.now(timezone.utc),
        "cookie_count": 10,
        "has_required_cookie": True,
        "message": "登录态文件已就绪",
    }


def test_session_expiry_notifies_only_on_transition(monkeypatch) -> None:
    connection = PlatformConnection(platform="weibo", status="connected", session_meta={})
    account = SimpleNamespace(platform_account_id="100", profile_url="https://weibo.com/u/100")
    adapter = MagicMock(check_login=AsyncMock(return_value=False))
    notification = MagicMock()
    db = MagicMock()

    monkeypatch.setattr(session_health, "_get_or_create_connection", lambda *args: connection)
    monkeypatch.setattr(session_health, "_lock_connection", lambda db, platform, fallback: fallback)
    monkeypatch.setattr(session_health, "_first_enabled_account", lambda *args: account)
    monkeypatch.setattr(session_health, "auth_state_status", _valid_auth_state)
    monkeypatch.setattr(session_health, "get_platform_adapter", lambda *args, **kwargs: adapter)
    monkeypatch.setattr(session_health, "_send_transition_notification", notification)

    first = session_health.check_platform_session(db, "weibo")
    second = session_health.check_platform_session(db, "weibo")

    assert first["transitioned"] is True
    assert second["transitioned"] is False
    assert connection.status == "expired"
    notification.assert_called_once()
    assert notification.call_args.kwargs["event_type"] == "login_expired"


def test_unconfigured_session_expiry_does_not_notify(monkeypatch) -> None:
    connection = PlatformConnection(platform="weibo", status="disconnected", session_meta={})
    notification = MagicMock()
    db = MagicMock()

    monkeypatch.setattr(session_health, "_get_or_create_connection", lambda *args: connection)
    monkeypatch.setattr(session_health, "_lock_connection", lambda db, platform, fallback: fallback)
    monkeypatch.setattr(
        session_health,
        "auth_state_status",
        lambda platform: {
            **_valid_auth_state(platform),
            "exists": False,
            "has_required_cookie": False,
        },
    )
    monkeypatch.setattr(session_health, "_send_transition_notification", notification)

    session_health.check_platform_session(db, "weibo")

    assert connection.status == "expired"
    notification.assert_not_called()


def test_session_recovery_notifies_and_enqueues_scan(monkeypatch) -> None:
    connection = PlatformConnection(
        platform="weibo",
        status="pending_login",
        session_meta={"status_before_login": "expired", "consecutive_failures": 1},
    )
    account = SimpleNamespace(platform_account_id="100", profile_url="https://weibo.com/u/100")
    adapter = MagicMock(check_login=AsyncMock(return_value=True))
    notification = MagicMock()
    enqueue_scan = MagicMock()
    db = MagicMock()

    monkeypatch.setattr(session_health, "_get_or_create_connection", lambda *args: connection)
    monkeypatch.setattr(session_health, "_lock_connection", lambda db, platform, fallback: fallback)
    monkeypatch.setattr(session_health, "_first_enabled_account", lambda *args: account)
    monkeypatch.setattr(session_health, "auth_state_status", _valid_auth_state)
    monkeypatch.setattr(session_health, "get_platform_adapter", lambda *args, **kwargs: adapter)
    monkeypatch.setattr(session_health, "_send_transition_notification", notification)
    monkeypatch.setattr(session_health, "enqueue_monitor_scan", enqueue_scan)

    result = session_health.check_platform_session(db, "weibo")

    assert result["recovered"] is True
    assert connection.status == "connected"
    assert connection.session_meta["consecutive_failures"] == 0
    assert "status_before_login" not in connection.session_meta
    notification.assert_called_once()
    assert notification.call_args.kwargs["event_type"] == "system"
    enqueue_scan.assert_called_once()


def test_transient_failure_requires_threshold(monkeypatch) -> None:
    connection = PlatformConnection(platform="weibo", status="connected", session_meta={})
    account = SimpleNamespace(platform_account_id="100", profile_url="https://weibo.com/u/100")
    adapter = MagicMock(check_login=AsyncMock(side_effect=RuntimeError("temporary network error")))
    notification = MagicMock()
    db = MagicMock()

    monkeypatch.setattr(session_health, "_get_or_create_connection", lambda *args: connection)
    monkeypatch.setattr(session_health, "_lock_connection", lambda db, platform, fallback: fallback)
    monkeypatch.setattr(session_health, "_first_enabled_account", lambda *args: account)
    monkeypatch.setattr(session_health, "auth_state_status", _valid_auth_state)
    monkeypatch.setattr(session_health, "get_platform_adapter", lambda *args, **kwargs: adapter)
    monkeypatch.setattr(session_health, "_send_transition_notification", notification)

    first = session_health.check_platform_session(db, "weibo", failure_threshold=2)
    second = session_health.check_platform_session(db, "weibo", failure_threshold=2)

    assert first["connection_status"] == "connected"
    assert second["connection_status"] == "failed"
    assert connection.session_meta["consecutive_failures"] == 2
    notification.assert_called_once()
