import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import ImportJob, MediaAsset, PlatformAccount, Post
from app.services.hashing import compute_content_hash
from app.services.media_queue import enqueue_pending_media_for_post_ids
from app.services.platform.registry import get_platform_adapter, resolve_platform_account_id
from app.services.worker_logs import finish_worker_run, start_worker_run, worker_status_from_result
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="import.run_job")
def run_import_job(job_id: int) -> dict:
    """Execute a history import job for one platform account."""
    db = SessionLocal()
    run_log = start_worker_run(
        db,
        worker_name="import",
        task_name="import.run_job",
        payload={"job_id": job_id},
    )

    def complete(result: dict) -> dict:
        finish_worker_run(
            db,
            run_log,
            status=worker_status_from_result(result),
            result=result,
            error_message=result.get("error"),
        )
        return result

    try:
        job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
        if job is None:
            return complete({"job_id": job_id, "status": "not_found"})

        account = db.query(PlatformAccount).filter(PlatformAccount.id == job.account_id).first()
        if account is None:
            job.status = "failed"
            job.error_message = "Account not found"
            db.commit()
            return complete({"job_id": job_id, "status": "failed", "error": "Account not found"})

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        storage_path = settings.platform_auth_state_path(account.platform)
        adapter = get_platform_adapter(account.platform, storage_state_path=storage_path)

        cursor = job.cursor
        limit = min(job.init_limit or 100, 50)
        processed = 0
        failed = 0
        total_fetched = 0
        queued_media_tasks = 0

        while True:
            if job.init_mode == "recent" and processed >= (job.init_limit or 100):
                break

            try:
                result = asyncio.run(
                    adapter.fetch_history_page(
                        account_id=resolve_platform_account_id(
                            account.platform,
                            account.platform_account_id,
                            account.profile_url,
                        ),
                        cursor=cursor,
                        limit=limit,
                    )
                )
            except Exception as exc:
                job.status = "failed"
                job.error_message = str(exc)[:500]
                db.commit()
                return complete({"job_id": job_id, "status": "failed", "error": str(exc)})

            if not result.items:
                break

            remaining = None
            if job.init_mode == "recent":
                remaining = max((job.init_limit or 100) - processed, 0)
            page_items = result.items[:remaining] if remaining is not None else result.items

            total_fetched += len(page_items)
            affected_post_ids: set[int] = set()
            for item in page_items:
                try:
                    content_hash = compute_content_hash(
                        platform=item.platform,
                        platform_post_id=item.platform_post_id,
                        full_text=item.full_text,
                        repost_text=item.repost_text,
                        image_urls=item.image_urls,
                        title=item.title,
                    )

                    existing = db.query(Post).filter(
                        Post.platform == item.platform,
                        Post.platform_post_id == item.platform_post_id,
                    ).first()

                    if existing is None:
                        post = Post(
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
                        db.add(post)
                        db.flush()
                        affected_post_ids.add(post.id)

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
                    else:
                        if existing.content_hash != content_hash:
                            existing.content_hash = content_hash
                            existing.raw_data = item.raw_data
                            existing.is_edited = True
                            existing.edit_count = (existing.edit_count or 0) + 1
                        existing.last_collected_at = datetime.now(timezone.utc)
                        affected_post_ids.add(existing.id)
                    processed += 1
                except Exception as exc:
                    failed += 1
                    logger.exception(
                        "Failed to import post platform=%s platform_post_id=%s job_id=%s",
                        getattr(item, "platform", None),
                        getattr(item, "platform_post_id", None),
                        job_id,
                    )
                    job.error_message = str(exc)[:500]

            job.imported_posts = processed
            job.total_posts = total_fetched
            job.failed_posts = failed
            job.cursor = result.next_cursor
            db.commit()
            queued_media_tasks += len(enqueue_pending_media_for_post_ids(db, affected_post_ids))

            if result.next_cursor is None:
                break
            if job.init_mode == "recent" and processed >= (job.init_limit or 100):
                break
            cursor = result.next_cursor

        job.status = "failed" if processed == 0 and failed > 0 else "completed"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return complete({
            "job_id": job_id,
            "status": job.status,
            "processed": processed,
            "failed": failed,
            "queued_media_tasks": queued_media_tasks,
        })

    except Exception as exc:
        logger.exception("import.run_job failed for job_id=%s", job_id)
        try:
            job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
            if job and job.status == "running":
                job.status = "failed"
                job.error_message = str(exc)[:500]
                db.commit()
        except Exception:
            pass
        return complete({"job_id": job_id, "status": "error", "error": str(exc)})
    finally:
        db.close()
