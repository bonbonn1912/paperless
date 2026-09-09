from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.services.export import export_service

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("")
def trigger_export(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    export_id = export_service.export_user_data(db, user)
    return {
        "export_id": export_id,
        "status": "ready",
        "message": f"Export created at exports/{export_id}/",
    }


@router.get("/{export_id}")
def get_export_status(
    export_id: str,
    user: CurrentUser,
) -> dict:
    from app.config import settings
    dest = settings.exports_dir / export_id
    if not dest.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return {
        "export_id": export_id,
        "status": "ready",
        "path": str(dest),
    }
