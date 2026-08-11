from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import Pagination


class PlatformAccountOut(BaseModel):
    id: int
    platform: str
    account_name: str
    profile_url: str
    platform_account_id: str | None = None
    check_interval: int = 300
    is_enabled: bool = True
    notification_enabled: bool = False
    init_mode: str = "recent"
    init_limit: int = 100
    status: str = "normal"
    last_checked_at: datetime | None = None
    last_post_published_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountCreateRequest(BaseModel):
    platform: str = Field(..., pattern=r"^(weibo|xueqiu)$")
    account_name: str = Field(..., min_length=1, max_length=255)
    profile_url: str = Field(..., min_length=1)
    platform_account_id: str | None = None
    check_interval: int = Field(default=300, ge=60)
    notification_enabled: bool = False
    init_mode: str = Field(default="recent", pattern=r"^(none|recent|all)$")
    init_limit: int = Field(default=100, ge=0)


class AccountUpdateRequest(BaseModel):
    account_name: str | None = Field(default=None, min_length=1, max_length=255)
    profile_url: str | None = Field(default=None, min_length=1)
    platform_account_id: str | None = None
    check_interval: int | None = Field(default=None, ge=60)
    is_enabled: bool | None = None
    notification_enabled: bool | None = None
    init_mode: str | None = Field(default=None, pattern=r"^(none|recent|all)$")
    init_limit: int | None = Field(default=None, ge=0)


class AccountPage(BaseModel):
    items: list[PlatformAccountOut]
    pagination: Pagination
