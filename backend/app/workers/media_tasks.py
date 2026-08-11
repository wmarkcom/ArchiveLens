import logging

from app.db.session import SessionLocal
from app.models import MediaAsset, PlatformAccount, Post
from app.services.media_downloader import MediaDownloader
from app.services.notifier import NotifierService
from app.services.worker_logs import finish_worker_run, start_worker_run, worker_status_from_result
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="media.download_asset")
def download_media_asset(asset_id: int) -> dict:
    """Download a single media asset to local disk."""
    db = SessionLocal()
    run_log = start_worker_run(
        db,
        worker_name="media",
        task_name="media.download_asset",
        payload={"asset_id": asset_id},
    )
    try:
        downloader = MediaDownloader(db)
        result = downloader.download_asset(asset_id)
        try:
            _notify_media_failure(db, asset_id, result)
        except Exception:
            logger.exception("Failed to send media notification for asset_id=%s", asset_id)
        finish_worker_run(db, run_log, status=worker_status_from_result(result), result=result, error_message=result.get("error"))
        return result
    except Exception as exc:
        logger.exception("download_media_asset failed for asset_id=%s", asset_id)
        result = {"asset_id": asset_id, "status": "error", "error": str(exc)}
        finish_worker_run(db, run_log, status="failed", result=result, error_message=str(exc))
        return result
    finally:
        db.close()


def _notify_media_failure(db, asset_id: int, result: dict) -> None:
    if result.get("status") not in {"failed", "error"}:
        return
    notifier = NotifierService(db)
    if not notifier.is_configured():
        return
    row = (
        db.query(MediaAsset, Post, PlatformAccount)
        .join(Post, MediaAsset.post_id == Post.id)
        .join(PlatformAccount, Post.account_id == PlatformAccount.id)
        .filter(MediaAsset.id == asset_id)
        .first()
    )
    if row is None:
        return
    asset, post, account = row
    if not account.notification_enabled:
        return
    notifier.send_event(
        event_type="media_download_failed",
        platform=asset.platform,
        title=f"媒体下载失败：{account.account_name}",
        body=f"资源 ID：{asset.id}\n错误：{result.get('error') or '未知错误'}\n原始地址：{asset.original_url}",
        reference_id=str(asset.id),
        reference_type="media_asset",
        payload=result,
    )
