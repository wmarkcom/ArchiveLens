import logging
from datetime import datetime, timedelta, timezone

from redis import Redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import PlatformAccount, PlatformConnection
from app.services.monitor import MonitorService
from app.services.worker_logs import finish_worker_run, start_worker_run, worker_status_from_result
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="monitor.check_account",
    soft_time_limit=settings.monitor_check_soft_time_limit,
    time_limit=settings.monitor_check_time_limit,
)
def check_account(account_id: int) -> dict:
    """Check an account for new or edited content."""
    db = SessionLocal()
    run_log = start_worker_run(
        db,
        worker_name="monitor",
        task_name="monitor.check_account",
        payload={"account_id": account_id},
    )
    try:
        service = MonitorService(db)
        result = service.check_account(account_id)
        finish_worker_run(db, run_log, status=worker_status_from_result(result), result=result, error_message=result.get("error"))
        return result
    except Exception as exc:
        logger.exception("check_account task failed for account_id=%s", account_id)
        result = {"account_id": account_id, "status": "error", "error": str(exc)}
        finish_worker_run(db, run_log, status="failed", result=result, error_message=str(exc))
        return result
    finally:
        _release_account_lock_safely(account_id)
        db.close()


@celery_app.task(name="monitor.scan_due_accounts")
def scan_due_accounts() -> dict:
    """Find enabled accounts due for checking and enqueue account-level monitor tasks."""
    db = SessionLocal()
    run_log = start_worker_run(
        db,
        worker_name="monitor",
        task_name="monitor.scan_due_accounts",
        payload={},
    )
    redis_client = _redis_client()
    now = datetime.now(timezone.utc)
    scanned = 0
    enqueued = 0
    skipped_locked = 0
    skipped_disconnected = 0

    try:
        connected_platforms = {
            row[0]
            for row in db.query(PlatformConnection.platform)
            .filter(PlatformConnection.status == "connected")
            .all()
        }
        accounts = (
            db.query(PlatformAccount)
            .filter(PlatformAccount.is_enabled.is_(True))
            .order_by(PlatformAccount.id.asc())
            .all()
        )

        for account in accounts:
            scanned += 1
            if account.platform not in connected_platforms:
                skipped_disconnected += 1
                continue
            if not _account_is_due(account, now):
                continue
            if not _acquire_account_lock(redis_client, account):
                skipped_locked += 1
                continue

            try:
                check_account.delay(account.id)
                enqueued += 1
            except Exception:
                _release_account_lock(redis_client, account.id)
                logger.exception("Failed to enqueue monitor check for account_id=%s", account.id)

        result = {
            "status": "success",
            "scanned": scanned,
            "enqueued": enqueued,
            "skipped_locked": skipped_locked,
            "skipped_disconnected": skipped_disconnected,
        }
        finish_worker_run(db, run_log, status="success", result=result)
        return result
    except Exception as exc:
        logger.exception("scan_due_accounts failed")
        result = {"status": "error", "error": str(exc)}
        finish_worker_run(db, run_log, status="failed", result=result, error_message=str(exc))
        return result
    finally:
        db.close()


def _redis_client() -> Redis:
    return Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )


def _account_is_due(account: PlatformAccount, now: datetime) -> bool:
    if account.last_checked_at is None:
        return True

    last_checked_at = account.last_checked_at
    if last_checked_at.tzinfo is None:
        last_checked_at = last_checked_at.replace(tzinfo=timezone.utc)

    interval = max(account.check_interval or 60, 60)
    return last_checked_at + timedelta(seconds=interval) <= now


def _acquire_account_lock(redis_client: Redis, account: PlatformAccount) -> bool:
    interval = max(account.check_interval or 60, 60)
    ttl = max(interval, settings.monitor_check_time_limit, settings.monitor_scan_interval * 2, 60)
    return bool(redis_client.set(_account_lock_key(account.id), "1", nx=True, ex=ttl))


def _release_account_lock(redis_client: Redis, account_id: int) -> None:
    try:
        redis_client.delete(_account_lock_key(account_id))
    except Exception:
        logger.exception("Failed to release monitor lock for account_id=%s", account_id)


def _release_account_lock_safely(account_id: int) -> None:
    try:
        _release_account_lock(_redis_client(), account_id)
    except Exception:
        logger.exception("Failed to create Redis client for releasing monitor lock account_id=%s", account_id)


def _account_lock_key(account_id: int) -> str:
    return f"archivelens:monitor:account:{account_id}:scheduled"
