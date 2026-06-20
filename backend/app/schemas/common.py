from __future__ import annotations

from pydantic import BaseModel, Field


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "ok"


class TaskAcceptedResponse(BaseModel):
    accepted: bool = True
    task_id: str | None = None
    message: str = "task accepted"
