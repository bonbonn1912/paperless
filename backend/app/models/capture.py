from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import generate_uuid, utc_now


class CaptureSession(Base):
    __tablename__ = "capture_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)  # draft | finalized | discarded
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    pages: Mapped[List["CapturePage"]] = relationship("CapturePage", back_populates="session", cascade="all, delete-orphan", order_by="CapturePage.page_number")


class CapturePage(Base):
    __tablename__ = "capture_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("capture_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("document_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rotation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0, 90, 180, 270
    crop_box: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    upload_status: Mapped[str] = mapped_column(String(32), default="uploaded", nullable=False)  # uploaded | processing | failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    session: Mapped["CaptureSession"] = relationship("CaptureSession", back_populates="pages")

    __table_args__ = (
        UniqueConstraint("session_id", "page_number", name="uq_session_page_num"),
    )
