from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class JobProgress(BaseModel):
    processed_pages: int = 0
    total_pages: int = 0


class JobSummary(BaseModel):
    id: str
    state: str
    step: str
    processed_pages: int = 0
    total_pages: int = 0
    attempt: int = 1
    updated_at: datetime
    next_run_at: Optional[datetime] = None
    error_code: Optional[str] = None


class JobEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    from_state: str
    to_state: str
    step: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    created_at: datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    document_id: Optional[str] = None
    run_id: str
    job_type: str
    state: str
    step: str
    priority: int
    progress: Optional[Dict[str, Any]] = None
    not_before: Optional[datetime] = None
    attempts: int
    max_attempts: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BatchStatusSummary(BaseModel):
    batch_id: str
    total: int
    uploaded: int
    upload_failed: int
    waiting_for_upload: int
    ready: int
    needs_review: int
    processing: int
    queued: int
    failed: int
    cancelled: int
    terminal: bool


class StatusItemSummary(BaseModel):
    batch_id: Optional[str] = None
    item_id: Optional[str] = None
    document_id: Optional[str] = None
    upload_state: Optional[str] = None
    processing_state: Optional[str] = None
    classification_state: Optional[str] = None
    index_state: Optional[str] = None
    review_reasons: List[str] = Field(default_factory=list)
    retryable: bool = False
    job: Optional[JobSummary] = None


class StatusPollRequest(BaseModel):
    batch_ids: List[str] = Field(default_factory=list)
    document_ids: List[str] = Field(default_factory=list)
    known_revision: Optional[str] = None


class StatusPollResponse(BaseModel):
    revision: str
    unchanged: bool = False
    batches: List[BatchStatusSummary] = Field(default_factory=list)
    items: List[StatusItemSummary] = Field(default_factory=list)
    poll_after_ms: int = 2000
