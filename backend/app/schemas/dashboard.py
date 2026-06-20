from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.posts import PostListItem
from app.schemas.notifications import NotificationEventOut


class HealthStatus(BaseModel):
    frontend: str = "normal"
    api: str = "normal"
    postgres: str = "normal"
    redis: str = "normal"
    worker: str = "normal"
    beat: str = "normal"
    media_worker: str = "normal"
    weibo_login: str = "normal"
    xueqiu_login: str = "warning"


class DashboardSummary(BaseModel):
    account_count: int = 0
    post_count: int = 0
    media_total_size: int = 0
    failed_task_count: int = 0
    recent_posts: list[PostListItem] = []
    health: HealthStatus = HealthStatus()
    recent_events: list[NotificationEventOut] = []
