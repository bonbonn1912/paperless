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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import generate_uuid, utc_now


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    document_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id: Mapped[str] = mapped_column(String(36), default=generate_uuid, nullable=False)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)  # base_pipeline | high_res_ocr | reindex | export | cleanup
    state: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)  # queued | running | succeeded | failed | cancelled | cancelling | scheduled | retry_wait
    step: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)  # 10=upload, 8=retry, 5=scheduled, 1=maintenance
    progress: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # {processed_pages: int, total_pages: int}
    not_before: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    schedule_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    events: Mapped[List["JobEvent"]] = relationship("JobEvent", back_populates="job", cascade="all, delete-orphan", order_by="JobEvent.id")

    __table_args__ = (
        Index("idx_jobs_claim", "state", "priority", "not_before", "created_at"),
        Index("idx_jobs_doc", "document_id", "state"),
    )


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    step: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    progress: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    job: Mapped["Job"] = relationship("Job", back_populates="events")
