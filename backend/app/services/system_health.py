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

    started_at = latest_log.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    stale_after = timedelta(seconds=max(settings.monitor_scan_interval * 3, 90))
    if datetime.now(timezone.utc) - started_at > stale_after:
        return HEALTH_WARNING

    return HEALTH_NORMAL
