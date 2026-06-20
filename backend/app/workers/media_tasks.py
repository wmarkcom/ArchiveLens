import logging

from app.db.session import SessionLocal
from app.services.media_downloader import MediaDownloader
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
        finish_worker_run(db, run_log, status=worker_status_from_result(result), result=result, error_message=result.get("error"))
        return result
    except Exception as exc:
        logger.exception("download_media_asset failed for asset_id=%s", asset_id)
        result = {"asset_id": asset_id, "status": "error", "error": str(exc)}
        finish_worker_run(db, run_log, status="failed", result=result, error_message=str(exc))
        return result
    finally:
        db.close()
