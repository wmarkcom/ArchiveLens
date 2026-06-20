from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SystemSettingOut(BaseModel):
    id: int
    key: str
    value: str | None = None
    value_type: str = "string"
    description: str | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingItem(BaseModel):
    key: str
    value: str | None = None


class SettingsBulkUpdateRequest(BaseModel):
    settings: list[SettingItem]
