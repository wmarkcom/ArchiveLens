from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import Pagination


class MediaAssetOut(BaseModel):
    id: int
    post_id: int
    platform: str
    platform_post_id: str
    asset_type: str
    original_url: str
    local_path: str | None = None
    local_url: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    download_status: str = "pending"
    error_message: str | None = None
    retry_count: int = 0
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MediaAssetPage(BaseModel):
    items: list[MediaAssetOut]
    pagination: Pagination
