from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import require_admin_token
from app.db.session import get_db
from app.models import MediaAsset, PlatformAccount, Post, PostSnapshot
from app.schemas.posts import PostDetail, PostListItem, PostPage, PostSnapshotOut
from app.schemas.common import Pagination
from app.services.media_urls import media_asset_preview_url, media_asset_to_out

router = APIRouter(dependencies=[Depends(require_admin_token)])


def _post_to_list_item(post: Post, account_name: str, cover_asset: MediaAsset | None = None) -> PostListItem:
    return PostListItem(
        id=post.id,
        platform=post.platform,
        account_name=account_name,
        platform_post_id=post.platform_post_id,
        original_url=post.original_url,
        published_at=post.published_at,
        title=post.title,
        full_text=(post.full_text or "")[:200],
        status=post.status,
        is_edited=post.is_edited,
        edit_count=post.edit_count,
        media_count=len(post.image_urls or []) + len(post.video_cover_urls or []),
        cover_url=media_asset_preview_url(cover_asset),
        last_collected_at=post.last_collected_at,
    )


def _cover_assets_by_post_id(db: Session, post_ids: set[int]) -> dict[int, MediaAsset]:
    if not post_ids:
        return {}
    assets = (
        db.query(MediaAsset)
        .filter(MediaAsset.post_id.in_(post_ids))
        .order_by(MediaAsset.post_id.asc(), MediaAsset.asset_type.asc(), MediaAsset.sort_order.asc(), MediaAsset.id.asc())
        .all()
    )
    covers: dict[int, MediaAsset] = {}
    for asset in assets:
        covers.setdefault(asset.post_id, asset)
    return covers


@router.get("", response_model=PostPage)
def list_posts(
    platform: str | None = Query(default=None),
    account_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PostPage:
    q = db.query(Post)
    if platform:
        q = q.filter(Post.platform == platform)
    if account_id:
        q = q.filter(Post.account_id == account_id)
    if status:
        q = q.filter(Post.status == status)
    if keyword:
        keyword_like = f"%{keyword}%"
        q = q.join(PlatformAccount, Post.account_id == PlatformAccount.id).filter(
            or_(
                Post.full_text.ilike(keyword_like),
                Post.title.ilike(keyword_like),
                PlatformAccount.account_name.ilike(keyword_like),
                PlatformAccount.platform_account_id.ilike(keyword_like),
            )
        )
    total = q.count()
    rows = (
        q.order_by(Post.published_at.desc().nullslast(), Post.last_collected_at.desc(), Post.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    account_ids = {row.account_id for row in rows}
    accounts = {a.id: a.account_name for a in db.query(PlatformAccount).filter(PlatformAccount.id.in_(account_ids)).all()}
    covers = _cover_assets_by_post_id(db, {row.id for row in rows})

    items = [_post_to_list_item(row, accounts.get(row.account_id, ""), covers.get(row.id)) for row in rows]
    return PostPage(items=items, pagination=Pagination(page=page, page_size=page_size, total=total))


@router.get("/{post_id}", response_model=PostDetail)
def get_post(post_id: int, db: Session = Depends(get_db)) -> PostDetail:
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="内容不存在")
    account = db.query(PlatformAccount).filter(PlatformAccount.id == post.account_id).first()
    media_assets = (
        db.query(MediaAsset)
        .filter(MediaAsset.post_id == post.id)
        .order_by(MediaAsset.asset_type.asc(), MediaAsset.sort_order.asc(), MediaAsset.id.asc())
        .all()
    )
    return PostDetail(
        id=post.id,
        platform=post.platform,
        account_id=post.account_id,
        account_name=account.account_name if account else "",
        platform_post_id=post.platform_post_id,
        original_url=post.original_url,
        published_at=post.published_at,
        title=post.title,
        full_text=post.full_text,
        repost_text=post.repost_text,
        image_urls=post.image_urls or [],
        video_cover_urls=post.video_cover_urls or [],
        media_assets=[media_asset_to_out(asset) for asset in media_assets],
        source=post.source,
        content_hash=post.content_hash,
        is_edited=post.is_edited,
        edit_count=post.edit_count,
        status=post.status,
        error_message=post.error_message,
        missing_count=post.missing_count,
        last_collected_at=post.last_collected_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.get("/{post_id}/snapshots", response_model=list[PostSnapshotOut])
def list_snapshots(post_id: int, db: Session = Depends(get_db)) -> list[PostSnapshotOut]:
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="内容不存在")
    rows = db.query(PostSnapshot).filter(PostSnapshot.post_id == post_id).order_by(PostSnapshot.version.desc()).all()
    return [PostSnapshotOut.model_validate(row) for row in rows]
