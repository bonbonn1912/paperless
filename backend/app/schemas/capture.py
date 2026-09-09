from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CapturePagePatch(BaseModel):
    page_id: str
    page_number: int
    rotation: int = 0  # 0, 90, 180, 270
    crop_box: Optional[Dict[str, Any]] = None


class CaptureSessionPatch(BaseModel):
    revision: int
    pages: List[CapturePagePatch]


class CapturePageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    asset_id: str
    page_number: int
    rotation: int
    crop_box: Optional[Dict[str, Any]] = None
    upload_status: str
    created_at: datetime


class CaptureSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    status: str
    revision: int
    expires_at: datetime
    pages: List[CapturePageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CaptureFinalizeRequest(BaseModel):
    ordered_page_ids: List[str]
    draft_revision: int
    title: Optional[str] = None
