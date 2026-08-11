from celery import Celery
from celery.schedules import crontab

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
    task_track_started=True,
    worker_prefetch_multiplier=1,
    imports=[
        "app.workers.health_tasks",
        "app.workers.notification_tasks",
        "app.workers.monitor_tasks",
        "app.workers.import_tasks",
        "app.workers.media_tasks",
    ],
    beat_schedule={
        "monitor.scan_due_accounts": {
            "task": "monitor.scan_due_accounts",
            "schedule": settings.monitor_scan_interval,
            "options": {"expires": max(settings.monitor_scan_interval * 2, 60)},
        },
        "health.daily_check": {
            "task": "health.daily_check",
            "schedule": crontab(
                hour=settings.daily_health_check_hour,
                minute=settings.daily_health_check_minute,
            ),
            "options": {"expires": 3600},
        },
    },
    task_routes={
        "media.download_asset": {"queue": "media"},
    },
)
