from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import MediaAsset, PlatformAccount, PlatformConnection, Post, PostSnapshot
from app.services.hashing import compute_content_hash
from app.services.media_queue import enqueue_pending_media_for_post_ids
from app.services.platform.base import NormalizedPost
from app.services.platform.registry import get_platform_adapter, resolve_platform_account_id

logger = logging.getLogger(__name__)


class MonitorService:
    """Service that checks a platform account for new or edited content."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def check_account(self, account_id: int) -> dict:
        """Check an account for new/edited posts. Creates Posts, Snapshots, and MediaAssets."""
        account = self._db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()
        if account is None:
            return {"account_id": account_id, "status": "not_found"}
        if not account.is_enabled:
            return {"account_id": account_id, "status": "disabled"}

        connection = self._db.query(PlatformConnection).filter(
            PlatformConnection.platform == account.platform
        ).first()

        if connection is None or connection.status != "connected":
            return {"account_id": account_id, "status": "platform_not_connected"}

        try:
            storage_path = _resolve_storage_path(account.platform)
            adapter = get_platform_adapter(account.platform, storage_state_path=storage_path)
            platform_account_id = resolve_platform_account_id(
                account.platform,
                account.platform_account_id,
                account.profile_url,
            )
            result = asyncio.run(
                adapter.fetch_recent_posts(
                    account_id=platform_account_id,
                    limit=20,
                )
            )
            items = result.items
            platform_post_ids = [item.platform_post_id for item in items]
            existing_by_platform_post_id = {}
            if platform_post_ids:
                existing_by_platform_post_id = {
                    post.platform_post_id: post
                    for post in self._db.query(Post)
                    .filter(
                        Post.platform == account.platform,
                        Post.platform_post_id.in_(platform_post_ids),
                    )
                    .all()
                }
            detail_candidates = [
                item
                for item in items
                if adapter.should_fetch_detail_for_monitor(
                    item,
                    is_new=item.platform_post_id not in existing_by_platform_post_id,
                )
            ]
            if detail_candidates:
                enriched_candidates = asyncio.run(
                    adapter.enrich_posts_with_details(
                        platform_account_id,
                        detail_candidates,
                        max_count=settings.weibo_detail_fallback_limit,
                    )
                )
                enriched_by_platform_post_id = {item.platform_post_id: item for item in enriched_candidates}
                items = [enriched_by_platform_post_id.get(item.platform_post_id, item) for item in items]

            new_count = 0
            edited_count = 0
            affected_post_ids: set[int] = set()

            for item in items:
                existing = existing_by_platform_post_id.get(item.platform_post_id)

                new_hash = compute_content_hash(
                    platform=item.platform,
                    platform_post_id=item.platform_post_id,
                    full_text=item.full_text,
                    repost_text=item.repost_text,
                    image_urls=item.image_urls,
                    title=item.title,
                )

                if existing is None:
                    post = _create_post(account, item, new_hash)
                    self._db.add(post)
                    self._db.flush()
                    _create_media_assets(self._db, post, item)
                    affected_post_ids.add(post.id)
                    new_count += 1
                elif existing.content_hash != new_hash:
                    _create_snapshot(self._db, existing)
                    _update_post(existing, item, new_hash)
                    affected_post_ids.add(existing.id)
                    edited_count += 1
                else:
                    existing.missing_count = 0
                    existing.last_collected_at = datetime.now(timezone.utc)

            latest_published_at = max(
                (item.published_at for item in items if item.published_at is not None),
                default=None,
            )
            if latest_published_at is not None:
                if latest_published_at.tzinfo is None:
                    latest_published_at = latest_published_at.replace(tzinfo=timezone.utc)
                account.last_post_published_at = latest_published_at
            account.last_checked_at = datetime.now(timezone.utc)
            account.status = "normal"
            account.error_message = None
            self._db.commit()
            queued_media_tasks = len(enqueue_pending_media_for_post_ids(self._db, affected_post_ids))

            return {
                "account_id": account_id,
                "status": "success",
                "new_posts": new_count,
                "edited_posts": edited_count,
                "queued_media_tasks": queued_media_tasks,
            }
        except Exception as exc:
            logger.exception("Monitor check failed for account %s", account_id)
            account.status = "failed"
            account.error_message = str(exc)[:500]
            self._db.commit()
            return {"account_id": account_id, "status": "failed", "error": str(exc)}


def _resolve_storage_path(platform: str) -> Path:
    return settings.platform_auth_state_path(platform)


def _create_post(account: PlatformAccount, item: NormalizedPost, content_hash: str) -> Post:
    return Post(
        account_id=account.id,
        platform=item.platform,
        platform_post_id=item.platform_post_id,
        original_url=item.original_url,
        published_at=item.published_at,
        title=item.title,
        full_text=item.full_text,
        repost_text=item.repost_text,
        image_urls=item.image_urls,
        video_cover_urls=item.video_cover_urls,
        source=item.source,
        content_hash=content_hash,
        raw_data=item.raw_data,
        is_edited=item.is_edited,
        edit_count=0,
        status="normal",
        last_collected_at=datetime.now(timezone.utc),
    )


def _update_post(post: Post, item: NormalizedPost, content_hash: str) -> None:
    post.title = item.title
    post.full_text = item.full_text
    post.repost_text = item.repost_text
    post.image_urls = item.image_urls
    post.video_cover_urls = item.video_cover_urls
    post.source = item.source
    post.content_hash = content_hash
    post.raw_data = item.raw_data
    post.is_edited = True
    post.edit_count = (post.edit_count or 0) + 1
    post.status = "edited"
    post.last_collected_at = datetime.now(timezone.utc)


def _create_snapshot(db: Session, post: Post) -> None:
    version = (post.edit_count or 0) + 1
    snapshot = PostSnapshot(
        post_id=post.id,
        version=version,
        platform_post_id=post.platform_post_id,
        original_url=post.original_url,
        published_at=post.published_at,
        title=post.title,
        full_text=post.full_text,
        repost_text=post.repost_text,
        image_urls=post.image_urls or [],
        video_cover_urls=post.video_cover_urls or [],
        source=post.source,
        content_hash=post.content_hash,
        raw_data=post.raw_data or {},
    )
    db.add(snapshot)


def _create_media_assets(db: Session, post: Post, item: NormalizedPost) -> None:
    for idx, url in enumerate(item.image_urls or []):
        db.add(
            MediaAsset(
                post_id=post.id,
                platform=post.platform,
                platform_post_id=post.platform_post_id,
                asset_type="image",
                original_url=url,
                sort_order=idx,
            )
        )
    for idx, url in enumerate(item.video_cover_urls or []):
        db.add(
            MediaAsset(
                post_id=post.id,
                platform=post.platform,
                platform_post_id=post.platform_post_id,
                asset_type="video_cover",
                original_url=url,
                sort_order=idx,
            )
        )
