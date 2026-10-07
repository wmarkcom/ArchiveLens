import logging

logger = logging.getLogger(__name__)


def enqueue_monitor_scan() -> str | None:
    try:
        from app.workers.monitor_tasks import scan_due_accounts

        return str(scan_due_accounts.delay().id)
    except Exception:
        logger.exception("Failed to enqueue monitor scan")
        return None


def enqueue_platform_session_check(platform: str) -> str | None:
    try:
        from app.workers.health_tasks import check_platform_sessions

        return str(check_platform_sessions.delay(platform).id)
    except Exception:
        logger.exception("Failed to enqueue platform session check")
        return None
