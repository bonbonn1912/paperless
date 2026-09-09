from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FolderBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: Optional[str] = None


class FolderCreate(FolderBase):
    pass


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[str] = None


class FolderResponse(FolderBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    document_count: int = 0
    created_at: datetime
    children: List["FolderResponse"] = Field(default_factory=list)
