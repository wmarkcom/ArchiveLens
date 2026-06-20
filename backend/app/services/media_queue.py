from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import MediaAsset

logger = logging.getLogger(__name__)


def enqueue_media_downloads(asset_ids: list[int]) -> list[str]:
    """Queue media download tasks without failing the caller if Redis/Celery is unavailable."""
    if not asset_ids:
        return []

    from app.workers.media_tasks import download_media_asset

    task_ids: list[str] = []
    for asset_id in asset_ids:
        try:
            task = download_media_asset.delay(asset_id)
            task_ids.append(task.id)
        except Exception:
            logger.exception("Failed to enqueue media download task for asset_id=%s", asset_id)
    return task_ids


def enqueue_pending_media_for_post_ids(db: Session, post_ids: set[int]) -> list[str]:
    """Queue all pending media assets that belong to the given posts."""
    if not post_ids:
        return []

    rows = (
        db.query(MediaAsset.id)
        .filter(MediaAsset.post_id.in_(post_ids))
        .filter(MediaAsset.download_status == "pending")
        .order_by(MediaAsset.id.asc())
        .all()
    )
    return enqueue_media_downloads([row[0] for row in rows])
