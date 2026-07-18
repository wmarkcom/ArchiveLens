from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.models import PlatformAccount, PlatformConnection
from app.services import monitor as monitor_module
from app.services.monitor import MonitorService
from app.services.platform.base import PlatformAuthenticationError
from app.services import system_health
from app.workers.celery_app import celery_app


def test_monitor_marks_platform_expired_and_stops_future_scheduling(monkeypatch) -> None:
    account = PlatformAccount(
        id=1,
        platform="weibo",
        account_name="测试账号",
        profile_url="https://weibo.com/u/1002568141",
        platform_account_id="1002568141",
        check_interval=300,
        is_enabled=True,
        init_mode="recent",
        init_limit=20,
        status="normal",
    )
    connection = PlatformConnection(platform="weibo", status="connected")
    account_query = MagicMock()
    account_query.filter.return_value.first.return_value = account
    connection_query = MagicMock()
    connection_query.filter.return_value.first.return_value = connection
    db = MagicMock()
    db.query.side_effect = [account_query, connection_query]

    adapter = MagicMock()
    adapter.fetch_recent_posts = AsyncMock(
        side_effect=PlatformAuthenticationError("微博登录态已失效，请重新登录")
    )
    monkeypatch.setattr(monitor_module, "get_platform_adapter", lambda *args, **kwargs: adapter)

    result = MonitorService(db).check_account(account.id)

    assert result["auth_expired"] is True
    assert connection.status == "expired"
    assert account.status == "failed"
    assert account.last_checked_at is not None
    db.commit.assert_called_once()


def test_monitor_applies_account_interval_backoff_after_transient_failure(monkeypatch) -> None:
    account = PlatformAccount(
        id=2,
        platform="weibo",
        account_name="测试账号",
        profile_url="https://weibo.com/u/1002568141",
        platform_account_id="1002568141",
        check_interval=300,
        is_enabled=True,
        init_mode="recent",
        init_limit=20,
        status="normal",
    )
    connection = PlatformConnection(platform="weibo", status="connected")
    account_query = MagicMock()
    account_query.filter.return_value.first.return_value = account
    connection_query = MagicMock()
    connection_query.filter.return_value.first.return_value = connection
    db = MagicMock()
    db.query.side_effect = [account_query, connection_query]

    adapter = MagicMock()
    adapter.fetch_recent_posts = AsyncMock(side_effect=RuntimeError("temporary network error"))
    monkeypatch.setattr(monitor_module, "get_platform_adapter", lambda *args, **kwargs: adapter)

    result = MonitorService(db).check_account(account.id)

    assert result["status"] == "failed"
    assert connection.status == "connected"
    assert account.last_checked_at is not None


def test_queue_health_reports_warning_and_error(monkeypatch) -> None:
    class FakeRedis:
        def llen(self, queue_name: str) -> int:
            return {"celery": 150, "media": 2500}[queue_name]

    monkeypatch.setattr(system_health.Redis, "from_url", lambda *args, **kwargs: FakeRedis())
    monkeypatch.setattr(system_health.settings, "monitor_queue_warning_threshold", 100)
    monkeypatch.setattr(system_health.settings, "monitor_queue_critical_threshold", 500)
    monkeypatch.setattr(system_health.settings, "media_queue_warning_threshold", 500)
    monkeypatch.setattr(system_health.settings, "media_queue_critical_threshold", 2000)

    monitor_status, monitor_depth, media_status, media_depth = system_health.check_celery_queues()

    assert (monitor_status, monitor_depth) == (system_health.HEALTH_WARNING, 150)
    assert (media_status, media_depth) == (system_health.HEALTH_ERROR, 2500)


def test_monitor_worker_health_detects_stale_running_scan() -> None:
    latest_log = SimpleNamespace(
        status="running",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        finished_at=None,
    )
    query = MagicMock()
    query.filter.return_value.order_by.return_value.first.return_value = latest_log
    db = MagicMock()
    db.query.return_value = query

    assert system_health.check_monitor_worker(db, system_health.HEALTH_NORMAL) == system_health.HEALTH_ERROR


def test_celery_monitor_tasks_expire_and_prefetch_one_at_a_time() -> None:
    schedule = celery_app.conf.beat_schedule["monitor.scan_due_accounts"]

    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert schedule["options"]["expires"] >= 60
