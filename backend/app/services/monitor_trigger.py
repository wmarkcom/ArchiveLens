import logging

logger = logging.getLogger(__name__)


def enqueue_monitor_scan() -> str | None:
    try:
        from app.workers.monitor_tasks import scan_due_accounts

        return str(scan_due_accounts.delay().id)
    except Exception:
        logger.exception("Failed to enqueue monitor scan")
        return None
