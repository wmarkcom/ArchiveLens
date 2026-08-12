from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PlatformAccount, PlatformConnection, WorkerRunLog
from app.services.platform.registry import get_platform_adapter, resolve_platform_account_id
from app.workers.celery_app import celery_app


HEALTH_NORMAL = "normal"
HEALTH_WARNING = "warning"
HEALTH_ERROR = "error"
BEAT_HEARTBEAT_KEY = f"archivelens:{settings.app_env}:health:beat"


def check_redis() -> str:
    try:
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        return HEALTH_NORMAL if client.ping() else HEALTH_ERROR
    except Exception:
        return HEALTH_ERROR


def check_postgres(db: Session) -> str:
    try:
        db.execute(text("SELECT 1"))
        return HEALTH_NORMAL
    except Exception:
        return HEALTH_ERROR


def check_celery_workers() -> tuple[str, str]:
    try:
        inspector = celery_app.control.inspect(timeout=1)
        ping_replies = inspector.ping() or {}
        active_queues = inspector.active_queues() or {}
    except Exception:
        return HEALTH_ERROR, HEALTH_ERROR

    if not ping_replies:
        return HEALTH_ERROR, HEALTH_ERROR

    worker_online = False
    media_worker_online = False
    for queues in active_queues.values():
        queue_names = {str(queue.get("name")) for queue in queues or [] if isinstance(queue, dict)}
        if "media" in queue_names:
            media_worker_online = True
        if queue_names.intersection({"celery", "default"}):
            worker_online = True

    return (
        HEALTH_NORMAL if worker_online else HEALTH_ERROR,
        HEALTH_NORMAL if media_worker_online else HEALTH_ERROR,
    )


def check_monitor_worker(db: Session, celery_status: str) -> str:
    if celery_status != HEALTH_NORMAL:
        return HEALTH_ERROR

    latest_log = (
        db.query(WorkerRunLog)
        .filter(WorkerRunLog.task_name == "monitor.scan_due_accounts")
        .order_by(WorkerRunLog.started_at.desc(), WorkerRunLog.id.desc())
        .first()
    )
    if latest_log is None:
        return HEALTH_WARNING

    now = datetime.now(timezone.utc)
    started_at = _as_utc(latest_log.started_at)
    stale_after = timedelta(seconds=max(settings.monitor_scan_interval * 3, 90))
    if latest_log.status == "running":
        return HEALTH_ERROR if now - started_at > stale_after else HEALTH_NORMAL

    reference_time = _as_utc(latest_log.finished_at or latest_log.started_at)
    if now - reference_time > stale_after:
        return HEALTH_ERROR
    if latest_log.status == "failed":
        return HEALTH_ERROR
    return HEALTH_NORMAL


def check_celery_queues() -> tuple[str, int, str, int]:
    try:
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        monitor_depth = int(client.llen("celery"))
        media_depth = int(client.llen("media"))
    except Exception:
        return HEALTH_ERROR, -1, HEALTH_ERROR, -1

    return (
        _queue_status(
            monitor_depth,
            settings.monitor_queue_warning_threshold,
            settings.monitor_queue_critical_threshold,
        ),
        monitor_depth,
        _queue_status(
            media_depth,
            settings.media_queue_warning_threshold,
            settings.media_queue_critical_threshold,
        ),
        media_depth,
    )


def check_celery_beat() -> str:
    try:
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        return HEALTH_NORMAL if client.exists(BEAT_HEARTBEAT_KEY) else HEALTH_WARNING
    except Exception:
        return HEALTH_ERROR


def check_platform_logins(db: Session) -> dict[str, str]:
    statuses: dict[str, str] = {}
    accounts = {
        row.platform: row
        for row in db.query(PlatformAccount)
        .filter(PlatformAccount.is_enabled.is_(True))
        .order_by(PlatformAccount.id.asc())
        .all()
    }
    for platform in ("weibo", "xueqiu"):
        try:
            adapter = get_platform_adapter(
                platform,
                storage_state_path=settings.platform_auth_state_path(platform),
            )
            account = accounts.get(platform)
            account_id = (
                resolve_platform_account_id(platform, account.platform_account_id, account.profile_url)
                if account
                else None
            )
            statuses[platform] = HEALTH_NORMAL if asyncio.run(adapter.check_login(account_id)) else HEALTH_ERROR
        except Exception:
            statuses[platform] = HEALTH_ERROR
    return statuses


def collect_health_snapshot(db: Session, *, live_platform_check: bool = False) -> dict:
    celery_worker_status, media_worker_status = check_celery_workers()
    worker_status = check_monitor_worker(db, celery_worker_status)
    beat_status = check_celery_beat()
    monitor_queue_status, monitor_queue_depth, media_queue_status, media_queue_depth = check_celery_queues()
    connection_rows = db.query(PlatformConnection).order_by(PlatformConnection.platform).all()
    connection_statuses = {row.platform: row.status for row in connection_rows}
    if live_platform_check:
        platform_login_statuses = check_platform_logins(db)
    else:
        platform_login_statuses = {
            platform: HEALTH_NORMAL if status == "connected" else HEALTH_ERROR
            for platform, status in connection_statuses.items()
        }

    checks = {
        "postgres": check_postgres(db),
        "redis": check_redis(),
        "worker": worker_status,
        "beat": beat_status,
        "media_worker": media_worker_status,
        "monitor_queue": monitor_queue_status,
        "media_queue": media_queue_status,
        "weibo_login": platform_login_statuses.get("weibo", HEALTH_ERROR),
        "xueqiu_login": platform_login_statuses.get("xueqiu", HEALTH_ERROR),
    }
    failed_checks = [name for name, status in checks.items() if status == HEALTH_ERROR]
    warning_checks = [name for name, status in checks.items() if status == HEALTH_WARNING]
    overall = HEALTH_ERROR if failed_checks else HEALTH_WARNING if warning_checks else HEALTH_NORMAL
    enabled_accounts = db.query(PlatformAccount).filter(PlatformAccount.is_enabled.is_(True)).count()
    failed_accounts = (
        db.query(PlatformAccount)
        .filter(PlatformAccount.is_enabled.is_(True), PlatformAccount.status == "failed")
        .count()
    )

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "checks": checks,
        "failed_checks": failed_checks,
        "warning_checks": warning_checks,
        "queues": {
            "monitor": monitor_queue_depth,
            "media": media_queue_depth,
        },
        "connections": connection_statuses,
        "accounts": {
            "enabled": enabled_accounts,
            "failed": failed_accounts,
        },
    }


def _queue_status(depth: int, warning_threshold: int, critical_threshold: int) -> str:
    if depth >= critical_threshold:
        return HEALTH_ERROR
    if depth >= warning_threshold:
        return HEALTH_WARNING
    return HEALTH_NORMAL


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
