from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import generate_uuid, utc_now


class ClassificationResult(Base):
    __tablename__ = "classification_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    suggested_tags: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    suggested_fields: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    review_reasons: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ClassificationRule(Base):
    __tablename__ = "classification_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    conditions: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    target_tag_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
