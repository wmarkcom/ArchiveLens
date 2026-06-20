from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "archivelens",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    imports=[
        "app.workers.health_tasks",
        "app.workers.monitor_tasks",
        "app.workers.import_tasks",
        "app.workers.media_tasks",
    ],
    beat_schedule={
        "monitor.scan_due_accounts": {
            "task": "monitor.scan_due_accounts",
            "schedule": settings.monitor_scan_interval,
        },
    },
    task_routes={
        "media.download_asset": {"queue": "media"},
    },
)
