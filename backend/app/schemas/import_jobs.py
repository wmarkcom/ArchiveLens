from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import Pagination


class ImportJobOut(BaseModel):
    id: int
    account_id: int
    platform: str
    account_name: str
    init_mode: str
    init_limit: int = 0
    status: str = "pending"
    total_posts: int = 0
    imported_posts: int = 0
    failed_posts: int = 0
    cursor: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ImportJobPage(BaseModel):
    items: list[ImportJobOut]
    pagination: Pagination
