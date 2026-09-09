from __future__ import annotations

import uuid
from datetime import datetime, timezone
from app.db.session import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())
