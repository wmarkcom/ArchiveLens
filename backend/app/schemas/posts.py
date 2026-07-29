from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import Pagination
from app.schemas.media import MediaAssetOut


class PostListItem(BaseModel):
    id: int
    platform: str
    account_name: str = ""
    platform_post_id: str
    original_url: str
    published_at: datetime | None = None
    title: str | None = None
    full_text: str | None = None
    status: str = "normal"
    is_edited: bool = False
    edit_count: int = 0
    media_count: int = 0
    cover_url: str | None = None
    text_suspected_truncated: bool = False
    detail_enriched: bool = False
    detail_enrich_status: str = "unknown"
    detail_enrich_error: str | None = None
    last_collected_at: datetime

    model_config = {"from_attributes": True}


class PostDetail(BaseModel):
    id: int
    platform: str
    account_id: int
    account_name: str = ""
    platform_post_id: str
    original_url: str
    published_at: datetime | None = None
    title: str | None = None
    full_text: str | None = None
    repost_text: str | None = None
    image_urls: list[str] = []
    video_cover_urls: list[str] = []
    media_assets: list[MediaAssetOut] = []
    source: str | None = None
    content_hash: str | None = None
    is_edited: bool = False
    edit_count: int = 0
    status: str = "normal"
    error_message: str | None = None
    missing_count: int = 0
    text_suspected_truncated: bool = False
    detail_enriched: bool = False
    detail_enrich_status: str = "unknown"
    detail_enrich_error: str | None = None
    last_collected_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PostSnapshotOut(BaseModel):
    id: int
    post_id: int
    version: int
    platform_post_id: str
    original_url: str
    published_at: datetime | None = None
    title: str | None = None
    full_text: str | None = None
    repost_text: str | None = None
    image_urls: list[str] = []
    video_cover_urls: list[str] = []
    source: str | None = None
    content_hash: str | None = None
    raw_data: dict[str, Any] = {}
    captured_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class PostPage(BaseModel):
    items: list[PostListItem]
    pagination: Pagination
