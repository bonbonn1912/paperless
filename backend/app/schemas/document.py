from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tag import TagResponse
from app.schemas.folder import FolderResponse


class DocumentPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    extracted_text: str
    extraction_method: str
    ocr_confidence: Optional[float] = None
    page_state: str
    width: Optional[float] = None
    height: Optional[float] = None
    word_boxes: Optional[List[Dict[str, Any]]] = None


class DocumentAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    sha256: str
    mime_type: str
    byte_size: int
    created_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    original_name: str
    storage_key: str
    mime_type: str
    file_size: int
    sha256: str
    title: Optional[str] = None
    sender: Optional[str] = None
    document_date: Optional[date] = None
    due_date: Optional[date] = None
    amount: Optional[int] = None  # in cents
    amount_decimal: Optional[str] = None  # formatted decimal string e.g. "49.99"
    currency: Optional[str] = "EUR"
    source: str
    metadata_revision: int
    processing_state: str
    classification_state: str
    index_state: str
    tags: List[TagResponse] = Field(default_factory=list)
    folders: List[FolderResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    pages: List[DocumentPageResponse] = Field(default_factory=list)
    assets: List[DocumentAssetResponse] = Field(default_factory=list)
    field_overrides: Dict[str, Any] = Field(default_factory=dict)
    active_job_id: Optional[str] = None


class DocumentPatch(BaseModel):
    title: Optional[str] = None
    sender: Optional[str] = None
    document_date: Optional[date] = None
    due_date: Optional[date] = None
    amount_decimal: Optional[str] = None  # e.g. "12.50"
    currency: Optional[str] = None


class DocumentViewerManifest(BaseModel):
    document_id: str
    mime_type: str
    file_size: int
    total_pages: int
    pages: List[Dict[str, Any]]
    file_url: str
    thumbnail_url: str
    can_search: bool = True
