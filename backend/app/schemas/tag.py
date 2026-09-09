from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    kind: str = Field("topic", pattern="^(document_type|topic)$")
    color: Optional[str] = Field(None, max_length=32)


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    kind: Optional[str] = Field(None, pattern="^(document_type|topic)$")
    color: Optional[str] = Field(None, max_length=32)


class TagAliasCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TagNameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tag_id: str
    name: str
    normalized_name: str
    is_canonical: bool
    created_at: datetime


class TagResponse(TagBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    merged_into_id: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    document_count: int = 0
    created_at: datetime


class TagMergeRequest(BaseModel):
    target_tag_id: str


class TagResolveResponse(BaseModel):
    resolved_existing: bool
    tag_id: Optional[str] = None
    name: str
    similar_tags: List[TagResponse] = Field(default_factory=list)
