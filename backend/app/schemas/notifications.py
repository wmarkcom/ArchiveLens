from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import Pagination


class NotificationEventOut(BaseModel):
    id: int
    event_type: str
    platform: str | None = None
    channel: str
    title: str
    body: str | None = None
    reference_id: str | None = None
    reference_type: str | None = None
    status: str = "pending"
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationPage(BaseModel):
    items: list[NotificationEventOut]
    pagination: Pagination
