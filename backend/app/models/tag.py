from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import generate_uuid, utc_now


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="topic", nullable=False)  # document_type | topic
    color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    merged_into_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tags.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    aliases: Mapped[List["TagName"]] = relationship("TagName", back_populates="tag", cascade="all, delete-orphan")


class TagName(Base):
    __tablename__ = "tag_names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    tag: Mapped["Tag"] = relationship("Tag", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("owner", "normalized_name", name="uq_owner_normalized_tag_name"),
        Index("idx_tag_names_owner_norm", "owner", "normalized_name"),
    )


class DocumentTag(Base):
    __tablename__ = "document_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)  # manual | rule
    score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    tag: Mapped["Tag"] = relationship("Tag")

    __table_args__ = (
        UniqueConstraint("document_id", "tag_id", name="uq_doc_tag"),
    )


class DocumentTagOverride(Base):
    __tablename__ = "document_tag_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)  # confirmed | excluded
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    tag: Mapped["Tag"] = relationship("Tag")

    __table_args__ = (
        UniqueConstraint("document_id", "tag_id", name="uq_doc_tag_override"),
    )
