from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.models import MediaAsset
from app.schemas.common import Pagination, TaskAcceptedResponse
from app.schemas.media import MediaAssetOut, MediaAssetPage
from app.services.media_urls import media_asset_to_out
from app.workers.media_tasks import download_media_asset

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.get("", response_model=MediaAssetPage)
def list_media_assets(
    platform: str | None = Query(default=None),
    download_status: str | None = Query(default=None),
    asset_type: str | None = Query(default=None),
    post_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> MediaAssetPage:
    q = db.query(MediaAsset)
    if platform:
        q = q.filter(MediaAsset.platform == platform)
    if download_status:
        q = q.filter(MediaAsset.download_status == download_status)
    if asset_type:
        q = q.filter(MediaAsset.asset_type == asset_type)
    if post_id:
        q = q.filter(MediaAsset.post_id == post_id)
    total = q.count()
    rows = q.order_by(MediaAsset.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [media_asset_to_out(row) for row in rows]
    return MediaAssetPage(items=items, pagination=Pagination(page=page, page_size=page_size, total=total))


@router.get("/{asset_id}", response_model=MediaAssetOut)
def get_media_asset(asset_id: int, db: Session = Depends(get_db)) -> MediaAssetOut:
    asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()
    if asset is None:
        raise HTTPException(status_code=404, detail="媒体资源不存在")
    return media_asset_to_out(asset)


@router.post("/{asset_id}/retry-download", response_model=TaskAcceptedResponse)
def retry_download(asset_id: int, db: Session = Depends(get_db)) -> TaskAcceptedResponse:
    asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()
    if asset is None:
        raise HTTPException(status_code=404, detail="媒体资源不存在")
    if asset.download_status != "failed":
        raise HTTPException(status_code=400, detail="仅下载失败的资源可以重试")
    asset.download_status = "pending"
    asset.error_message = None
    db.commit()
    try:
        task = download_media_asset.delay(asset.id)
    except Exception as exc:
        asset.download_status = "failed"
        asset.error_message = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=503, detail=f"提交媒体下载任务失败：{exc}") from exc
    return TaskAcceptedResponse(task_id=task.id, message="媒体下载任务已重新排队")
