from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ScheduleBase(BaseModel):
    job_type: str = Field(..., pattern="^(high_res_ocr|reindex|export)$")
    filter_config: Dict[str, Any] = Field(default_factory=dict)
    mode: str = Field("scheduled", pattern="^(disabled|manual_only|immediate|scheduled)$")
    weekdays: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    local_time: str = Field("02:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    timezone: str = "Europe/Berlin"
    window_minutes: int = 180
    limits: Dict[str, Any] = Field(default_factory=dict)


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    filter_config: Optional[Dict[str, Any]] = None
    mode: Optional[str] = Field(None, pattern="^(disabled|manual_only|immediate|scheduled)$")
    weekdays: Optional[List[int]] = None
    local_time: Optional[str] = Field(None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    timezone: Optional[str] = None
    window_minutes: Optional[int] = None
    limits: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ScheduleResponse(ScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SchedulePreviewResponse(BaseModel):
    schedule_id: str
    affected_documents_count: int
    next_run_at: Optional[datetime] = None
