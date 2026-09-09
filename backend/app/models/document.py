from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import generate_uuid, utc_now


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Extracted or confirmed metadata
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    sender: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # in cents
    currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True, default="EUR")
    search_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of up to 50 background search terms

    source: Mapped[str] = mapped_column(String(32), default="upload", nullable=False)  # upload | capture
    metadata_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Distinct states per spec section 8
    processing_state: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)  # queued | processing | ready | failed
    classification_state: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending | classified | needs_review
    index_state: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending | partial | ready | failed

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    pages: Mapped[List["DocumentPage"]] = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number")
    assets: Mapped[List["DocumentAsset"]] = relationship("DocumentAsset", back_populates="document", cascade="all, delete-orphan")
    field_overrides: Mapped[List["DocumentFieldOverride"]] = relationship("DocumentFieldOverride", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_doc_owner_sha256", "owner", "sha256"),
        Index("idx_doc_owner_processing", "owner", "processing_state"),
        Index("idx_doc_owner_classification", "owner", "classification_state"),
    )


class DocumentAsset(Base):
    __tablename__ = "document_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    capture_session_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # source_image | assembled_pdf
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Optional["Document"]] = relationship("Document", back_populates="assets")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(32), default="direct", nullable=False)  # direct | ocr | mixed
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    page_state: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending | extracted | ocr_done | failed
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    height: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    word_boxes: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped["Document"] = relationship("Document", back_populates="pages")

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_doc_page"),
    )


class DocumentFieldOverride(Base):
    __tablename__ = "document_field_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    document: Mapped["Document"] = relationship("Document", back_populates="field_overrides")

    __table_args__ = (
        UniqueConstraint("document_id", "field_name", name="uq_doc_field_override"),
    )
