from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import generate_uuid, utc_now


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="in_progress", nullable=False)  # in_progress | completed | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    items: Mapped[List["UploadItem"]] = relationship("UploadItem", back_populates="batch", cascade="all, delete-orphan", order_by="UploadItem.position")


class UploadItem(Base):
    __tablename__ = "upload_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    client_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="waiting_for_upload", nullable=False)  # waiting_for_upload | uploading | accepted | failed | skipped
    document_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    batch: Mapped["UploadBatch"] = relationship("UploadBatch", back_populates="items")

    __table_args__ = (
        UniqueConstraint("batch_id", "client_item_id", name="uq_batch_client_item"),
        Index("idx_upload_item_status", "batch_id", "status"),
    )
