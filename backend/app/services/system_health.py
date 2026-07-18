from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import WorkerRunLog
from app.workers.celery_app import celery_app


HEALTH_NORMAL = "normal"
HEALTH_WARNING = "warning"
HEALTH_ERROR = "error"


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
    for worker_name, queues in active_queues.items():
        queue_names = {str(queue.get("name")) for queue in queues or [] if isinstance(queue, dict)}
        if "media" in queue_names:
            media_worker_online = True
        if "celery" in queue_names or "default" in queue_names:
            worker_online = True
        if "media" not in worker_name:
            worker_online = worker_online or bool(queue_names)

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


def check_celery_beat(db: Session) -> str:
    latest_log = (
        db.query(WorkerRunLog)
        .filter(WorkerRunLog.task_name == "monitor.scan_due_accounts")
        .order_by(WorkerRunLog.started_at.desc(), WorkerRunLog.id.desc())
        .first()
    )
    if latest_log is None:
        return HEALTH_WARNING

    if latest_log.status == "failed":
        return HEALTH_ERROR

    started_at = _as_utc(latest_log.started_at)

    stale_after = timedelta(seconds=max(settings.monitor_scan_interval * 3, 90))
    if datetime.now(timezone.utc) - started_at > stale_after:
        return HEALTH_WARNING

    return HEALTH_NORMAL


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
