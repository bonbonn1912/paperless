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


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("folders.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    children: Mapped[List["Folder"]] = relationship("Folder", backref="parent", remote_side=[id])

    __table_args__ = (
        UniqueConstraint("owner", "parent_id", "normalized_name", name="uq_owner_parent_normalized_folder"),
        Index("idx_folders_owner_norm", "owner", "normalized_name"),
    )


class DocumentFolder(Base):
    __tablename__ = "document_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    folder_id: Mapped[str] = mapped_column(String(36), ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True)

    folder: Mapped["Folder"] = relationship("Folder")

    __table_args__ = (
        UniqueConstraint("document_id", "folder_id", name="uq_doc_folder"),
    )
