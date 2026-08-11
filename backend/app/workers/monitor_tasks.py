import logging
from datetime import datetime, timedelta, timezone

from redis import Redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import PlatformAccount, PlatformConnection, Post
from app.services.monitor import MonitorService
from app.services.notifier import NotifierService
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
        try:
            _notify_monitor_result(db, account_id, result)
        except Exception:
            logger.exception("Failed to send monitor notification for account_id=%s", account_id)
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
        monitor_queue_depth = int(redis_client.llen("celery"))
        if monitor_queue_depth >= settings.monitor_queue_critical_threshold:
            result = {
                "status": "warning",
                "scanned": 0,
                "enqueued": 0,
                "skipped_locked": 0,
                "skipped_disconnected": 0,
                "queue_depth": monitor_queue_depth,
                "warning": "monitor queue backlog is above the critical threshold",
            }
            finish_worker_run(db, run_log, status="success", result=result)
            return result

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
            "queue_depth": monitor_queue_depth,
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


def _notify_monitor_result(db, account_id: int, result: dict) -> None:
    account = db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()
    if account is None:
        return
    notifier = NotifierService(db)
    if not account.notification_enabled or not notifier.is_configured():
        return

    account_reference = f"博主主页：{account.profile_url}"
    if result.get("auth_expired"):
        notifier.send_event(
            event_type="login_expired",
            platform=account.platform,
            title=f"{account.platform} 登录态已失效",
            body=f"博主：{account.account_name}\n{account_reference}",
            reference_id=str(account.id),
            reference_type="platform_account",
            payload=result,
        )
        return

    if result.get("status") in {"failed", "error"}:
        notifier.send_event(
            event_type="worker_error",
            platform=account.platform,
            title=f"{account.platform} 采集失败：{account.account_name}",
            body=f"错误：{result.get('error') or '未知错误'}\n{account_reference}",
            reference_id=str(account.id),
            reference_type="platform_account",
            payload=result,
        )
        return

    new_posts = int(result.get("new_posts") or 0)
    edited_posts = int(result.get("edited_posts") or 0)
    if new_posts:
        post_ids = [int(post_id) for post_id in result.get("new_post_ids") or []]
        notifier.send_event(
            event_type="new_post",
            platform=account.platform,
            title=f"发现新内容：{account.account_name}",
            body=_format_post_notification(
                db,
                account,
                post_ids,
                total_count=new_posts,
                account_reference=account_reference,
            ),
            reference_id=str(account.id),
            reference_type="platform_account",
            payload={**result, "notification_post_ids": post_ids},
        )
    if edited_posts:
        post_ids = [int(post_id) for post_id in result.get("edited_post_ids") or []]
        notifier.send_event(
            event_type="edited_post",
            platform=account.platform,
            title=f"内容发生更新：{account.account_name}",
            body=_format_post_notification(
                db,
                account,
                post_ids,
                total_count=edited_posts,
                account_reference=account_reference,
            ),
            reference_id=str(account.id),
            reference_type="platform_account",
            payload={**result, "notification_post_ids": post_ids},
        )


def _format_post_notification(
    db,
    account: PlatformAccount,
    post_ids: list[int],
    *,
    total_count: int,
    account_reference: str,
) -> str:
    posts = (
        db.query(Post)
        .filter(Post.id.in_(post_ids))
        .order_by(Post.published_at.desc().nullslast(), Post.id.desc())
        .limit(max(settings.notification_max_posts, 1))
        .all()
        if post_ids
        else []
    )
    lines = [f"博主：{account.account_name}", f"本次归档 {total_count} 条内容。", account_reference]
    for index, post in enumerate(posts, start=1):
        text = " ".join((post.full_text or post.title or "（无文字内容）").split())
        excerpt_limit = max(settings.notification_excerpt_length, 40)
        if len(text) > excerpt_limit:
            text = f"{text[:excerpt_limit].rstrip()}…"
        published_at = post.published_at.strftime("%Y-%m-%d %H:%M") if post.published_at else "时间未知"
        media_count = len(post.image_urls or []) + len(post.video_cover_urls or [])
        archive_url = _archive_post_url(post.id)
        lines.extend(
            [
                f"[{index}] {text}",
                f"发布时间：{published_at}｜媒体：{media_count} 个",
                f"归档详情：{archive_url}",
                f"微博原文：{post.original_url}",
            ]
        )
    remaining = total_count - len(posts)
    if remaining > 0:
        lines.append(f"其余 {remaining} 条请在内容归档中查看。")
    return "\n".join(lines)


def _archive_post_url(post_id: int) -> str:
    if settings.public_app_url:
        return f"{settings.public_app_url}/posts/{post_id}"
    return f"/posts/{post_id}"
