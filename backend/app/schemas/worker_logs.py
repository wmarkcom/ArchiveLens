from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import Pagination


class WorkerRunLogOut(BaseModel):
    id: int
    worker_name: str
    task_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    payload: dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkerRunLogPage(BaseModel):
    items: list[WorkerRunLogOut]
    pagination: Pagination
