from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PlatformAuthStateOut(BaseModel):
    platform: str
    exists: bool
    filename: str
    size_bytes: int | None = None
    updated_at: datetime | None = None
    cookie_count: int = 0
    has_required_cookie: bool = False
    message: str | None = None


class PlatformConnectionOut(BaseModel):
    id: int
    platform: str
    status: str
    session_data_encrypted: str | None = None
    auth_state: PlatformAuthStateOut | None = None
    last_login_at: datetime | None = None
    expired_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoginSession(BaseModel):
    id: str
    platform: str
    status: str
    login_url: str | None = None
    expires_at: datetime | None = None
    screenshot_url: str | None = None
    message: str | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}
