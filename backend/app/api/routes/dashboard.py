from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.models import (
    ImportJob,
    MediaAsset,
    NotificationEvent,
    PlatformAccount,
    PlatformConnection,
    Post,
)
from app.schemas.dashboard import DashboardSummary, HealthStatus
from app.schemas.notifications import NotificationEventOut
from app.schemas.posts import PostListItem
from app.services.media_urls import media_asset_preview_url
from app.services.system_health import (
    check_postgres,
    check_celery_beat,
    check_celery_queues,
    check_celery_workers,
    check_monitor_worker,
    check_redis,
)

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    account_count = db.query(PlatformAccount).count()
    post_count = db.query(Post).count()

    media_size = db.query(MediaAsset.file_size).filter(
        MediaAsset.download_status == "success",
        MediaAsset.file_size.isnot(None),
    ).all()
    media_total_size = sum(row[0] for row in media_size if row[0])

    failed_task_count = db.query(ImportJob).filter(ImportJob.status == "failed").count()

    recent_posts_rows = (
        db.query(Post, PlatformAccount.account_name)
        .join(PlatformAccount, Post.account_id == PlatformAccount.id)
        .order_by(Post.published_at.desc().nullslast(), Post.last_collected_at.desc(), Post.id.desc())
        .limit(10)
        .all()
    )
    post_ids = {p.id for p, _ in recent_posts_rows}
    media_assets = (
        db.query(MediaAsset)
        .filter(MediaAsset.post_id.in_(post_ids))
        .order_by(MediaAsset.post_id.asc(), MediaAsset.asset_type.asc(), MediaAsset.sort_order.asc(), MediaAsset.id.asc())
        .all()
        if post_ids
        else []
    )
    cover_assets: dict[int, MediaAsset] = {}
    for asset in media_assets:
        cover_assets.setdefault(asset.post_id, asset)
    recent_posts = [
        PostListItem(
            id=p.id,
            platform=p.platform,
            account_name=name,
            platform_post_id=p.platform_post_id,
            original_url=p.original_url,
            published_at=p.published_at,
            title=p.title,
            full_text=(p.full_text or "")[:200],
            status=p.status,
            is_edited=p.is_edited,
            edit_count=p.edit_count,
            media_count=len(p.image_urls or []) + len(p.video_cover_urls or []),
            cover_url=media_asset_preview_url(cover_assets.get(p.id)),
            last_collected_at=p.last_collected_at,
        )
        for p, name in recent_posts_rows
    ]

    # Health checks
    celery_worker_status, media_worker_status = check_celery_workers()
    worker_status = check_monitor_worker(db, celery_worker_status)
    monitor_queue_status, monitor_queue_depth, media_queue_status, media_queue_depth = check_celery_queues()
    weibo_conn = db.query(PlatformConnection).filter(PlatformConnection.platform == "weibo").first()
    weibo_login = "normal"
    if weibo_conn and weibo_conn.status == "expired":
        weibo_login = "expired"
    elif weibo_conn and weibo_conn.status == "failed":
        weibo_login = "error"

    xueqiu_conn = db.query(PlatformConnection).filter(PlatformConnection.platform == "xueqiu").first()
    xueqiu_login = "normal" if xueqiu_conn and xueqiu_conn.status == "connected" else "warning"

    health = HealthStatus(
        postgres=check_postgres(db),
        redis=check_redis(),
        worker=worker_status,
        beat=check_celery_beat(db),
        media_worker=media_worker_status,
        monitor_queue=monitor_queue_status,
        monitor_queue_depth=monitor_queue_depth,
        media_queue=media_queue_status,
        media_queue_depth=media_queue_depth,
        weibo_login=weibo_login,
        xueqiu_login=xueqiu_login,
    )

    recent_events_rows = (
        db.query(NotificationEvent)
        .order_by(NotificationEvent.created_at.desc())
        .limit(10)
        .all()
    )
    recent_events = [NotificationEventOut.model_validate(e) for e in recent_events_rows]

    return DashboardSummary(
        account_count=account_count,
        post_count=post_count,
        media_total_size=media_total_size,
        failed_task_count=failed_task_count,
        recent_posts=recent_posts,
        health=health,
        recent_events=recent_events,
    )
