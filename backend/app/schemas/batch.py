from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BatchItemCreate(BaseModel):
    client_item_id: str
    position: int = 0
    original_name: str
    file_size: int = 0
    mime_type: str = "application/octet-stream"


class BatchCreateRequest(BaseModel):
    items: List[BatchItemCreate] = Field(..., min_length=1)


class BatchCreateResponse(BaseModel):
    batch_id: str
    total_items: int
    max_batch_files: int
    upload_concurrency: int
    item_ids: dict[str, str]  # client_item_id -> server item_id


class UploadItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_id: str
    client_item_id: str
    position: int
    original_name: str
    file_size: int
    mime_type: str
    status: str
    document_id: Optional[str] = None
    job_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    total_items: int
    status: str
    items: List[UploadItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
