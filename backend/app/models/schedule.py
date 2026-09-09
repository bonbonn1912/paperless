from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import generate_uuid, utc_now


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)  # high_res_ocr | reindex | export
    filter_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="scheduled", nullable=False)  # disabled | manual_only | immediate | scheduled
    weekdays: Mapped[List[int]] = mapped_column(JSON, default=list, nullable=False)  # 0=Monday, 6=Sunday
    local_time: Mapped[str] = mapped_column(String(8), default="02:00", nullable=False)  # HH:MM
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Berlin", nullable=False)
    window_minutes: Mapped[int] = mapped_column(Integer, default=180, nullable=False)
    limits: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)  # cpu_limit, memory_mb, doc_limit
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
