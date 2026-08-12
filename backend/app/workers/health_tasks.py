from redis import Redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.notifier import NotifierService
from app.services.system_health import BEAT_HEARTBEAT_KEY, collect_health_snapshot
from app.services.worker_logs import finish_worker_run, start_worker_run
from app.workers.celery_app import celery_app


@celery_app.task(name="health.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="health.beat_heartbeat")
def beat_heartbeat() -> dict:
    ttl = max(settings.monitor_scan_interval * 3, 90)
    client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )
    client.set(BEAT_HEARTBEAT_KEY, "1", ex=ttl)
    return {"status": "success", "ttl": ttl}


@celery_app.task(name="health.daily_check")
def daily_health_check() -> dict:
    db = SessionLocal()
    run_log = start_worker_run(
        db,
        worker_name="health",
        task_name="health.daily_check",
        payload={"scheduled_time": f"{settings.daily_health_check_hour:02d}:{settings.daily_health_check_minute:02d}"},
    )
    try:
        snapshot = collect_health_snapshot(db, live_platform_check=True)
        event = NotifierService(db).send_event(
            event_type="system",
            title=f"ArchiveLens 每日健康检查：{_overall_label(snapshot['overall'])}",
            body=_format_health_message(snapshot),
            payload=snapshot,
        )
        task_status = "success" if event.status == "sent" else "failed"
        result = {
            "status": task_status,
            "overall": snapshot["overall"],
            "failed_checks": snapshot["failed_checks"],
            "warning_checks": snapshot["warning_checks"],
            "notification_status": event.status,
        }
        finish_worker_run(db, run_log, status=task_status, result=result, error_message=event.error_message)
        return result
    except Exception as exc:
        finish_worker_run(db, run_log, status="failed", error_message=str(exc))
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


def _overall_label(status: str) -> str:
    return {"normal": "正常", "warning": "有警告", "error": "有异常"}.get(status, status)


def _status_label(status: str) -> str:
    return {"normal": "正常", "warning": "警告", "error": "异常"}.get(status, status)


def _format_health_message(snapshot: dict) -> str:
    checks = snapshot["checks"]
    queues = snapshot["queues"]
    accounts = snapshot["accounts"]
    check_labels = {
        "postgres": "PostgreSQL",
        "redis": "Redis",
        "worker": "Worker",
        "beat": "Beat",
        "media_worker": "Media Worker",
        "weibo_login": "微博登录",
        "xueqiu_login": "雪球登录",
    }
    services = "、".join(
        f"{label}{_status_label(checks[key])}"
        for key, label in check_labels.items()
    )
    return (
        f"检查时间：{snapshot['checked_at']}\n"
        f"服务状态：{services}\n"
        f"队列深度：检查 {queues['monitor']}，媒体 {queues['media']}\n"
        f"账号状态：启用 {accounts['enabled']}，失败 {accounts['failed']}"
    )
