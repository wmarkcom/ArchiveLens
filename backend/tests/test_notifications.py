from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.config import settings
from app.schemas.accounts import AccountCreateRequest
from app.services.system_health import (
    HEALTH_ERROR,
    HEALTH_NORMAL,
    HEALTH_WARNING,
    check_celery_beat,
    check_celery_workers,
)
from app.services.notifier import NotifierService
from app.workers.monitor_tasks import _format_post_notification
from app.workers.celery_app import celery_app


def test_feishu_notification_card_contains_title_and_body() -> None:
    service = NotifierService(MagicMock())
    payload = service._build_feishu_message(
        SimpleNamespace(title="测试标题", body="测试正文")
    )

    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "ArchiveLens | 测试标题"
    assert payload["card"]["elements"][0]["text"]["content"] == "测试正文"


def test_notifier_uses_environment_webhook_when_database_setting_is_empty(monkeypatch) -> None:
    query = MagicMock()
    query.filter.return_value.first.return_value = None
    db = MagicMock()
    db.query.return_value = query
    monkeypatch.setattr(settings, "feishu_webhook", "https://example.com/feishu")

    assert NotifierService(db).is_configured() is True


def test_daily_health_check_is_scheduled_at_eight_pm() -> None:
    schedule = celery_app.conf.beat_schedule["health.daily_check"]["schedule"]

    assert schedule.hour == {20}
    assert schedule.minute == {0}


def test_beat_heartbeat_is_scheduled_with_monitor_scan() -> None:
    entry = celery_app.conf.beat_schedule["health.beat_heartbeat"]

    assert entry["task"] == "health.beat_heartbeat"
    assert entry["schedule"] == settings.monitor_scan_interval


def test_beat_health_uses_heartbeat_key(monkeypatch) -> None:
    client = MagicMock()
    client.exists.return_value = 1
    monkeypatch.setattr("app.services.system_health.Redis.from_url", lambda *args, **kwargs: client)

    assert check_celery_beat() == HEALTH_NORMAL

    client.exists.return_value = 0
    assert check_celery_beat() == HEALTH_WARNING


def test_account_notification_is_opt_in() -> None:
    payload = AccountCreateRequest(
        platform="weibo",
        account_name="测试博主",
        profile_url="https://weibo.com/u/123456",
    )

    assert payload.notification_enabled is False


def test_post_notification_contains_archive_detail_and_excerpt(monkeypatch) -> None:
    post = SimpleNamespace(
        id=123,
        full_text="这是一条需要发送到飞书的归档正文。",
        title=None,
        published_at=None,
        image_urls=["one", "two"],
        video_cover_urls=[],
        original_url="https://weibo.com/100/abc",
    )
    query = MagicMock()
    query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [post]
    db = MagicMock()
    db.query.return_value = query
    account = SimpleNamespace(account_name="测试博主")
    monkeypatch.setattr(settings, "public_app_url", "http://localhost:5173")

    body = _format_post_notification(
        db,
        account,
        [123],
        total_count=1,
        account_reference="博主主页：https://weibo.com/u/100",
    )

    assert "这是一条需要发送到飞书的归档正文" in body
    assert "归档详情：http://localhost:5173/posts/123" in body
    assert "微博原文：https://weibo.com/100/abc" in body


def test_worker_health_requires_a_default_queue_for_monitor_worker() -> None:
    inspector = MagicMock()
    inspector.ping.return_value = {"celery@random-host": {"ok": "pong"}}
    inspector.active_queues.return_value = {
        "celery@random-host": [{"name": "media"}],
    }

    original_inspect = celery_app.control.inspect
    celery_app.control.inspect = MagicMock(return_value=inspector)
    try:
        worker_status, media_worker_status = check_celery_workers()
    finally:
        celery_app.control.inspect = original_inspect

    assert worker_status == HEALTH_ERROR
    assert media_worker_status == HEALTH_NORMAL
