from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReviewConfirmRequest(BaseModel):
    tag_ids: List[str] = Field(default_factory=list)
    excluded_tag_ids: List[str] = Field(default_factory=list)
    field_overrides: Dict[str, Any] = Field(default_factory=dict)
    mark_as_reviewed: bool = True
    create_rule: bool = False
    rule_name: Optional[str] = None


class BulkReviewRequest(BaseModel):
    document_ids: List[str] = Field(..., min_length=1)
    add_tag_ids: List[str] = Field(default_factory=list)
    remove_tag_ids: List[str] = Field(default_factory=list)
    mark_as_reviewed: bool = True


class BulkReviewResultItem(BaseModel):
    document_id: str
    success: bool
    error: Optional[str] = None


class BulkReviewResponse(BaseModel):
    results: List[BulkReviewResultItem]
