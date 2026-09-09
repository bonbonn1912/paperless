from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    owner: str
    preferences: Dict[str, Any] = Field(default_factory=dict)
    pinned_tabs: List[str] = Field(default_factory=list)


class SettingsUpdate(BaseModel):
    preferences: Optional[Dict[str, Any]] = None
    pinned_tabs: Optional[List[str]] = None


class CapabilitiesResponse(BaseModel):
    max_upload_mb: int
    max_batch_files: int
    upload_concurrency: int
    status_max_items: int
    max_capture_pages: int
    max_capture_total_mb: int
    max_assembled_pdf_mb: int
    heavy_job_concurrency: int
    heavy_cpu_limit: int
    heavy_memory_mb: int
    supported_mimes: List[str]
    available_ocr_languages: List[str]
