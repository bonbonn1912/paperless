from __future__ import annotations

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.capture import CapturePage, CaptureSession
from app.schemas.capture import (
    CaptureFinalizeRequest,
    CapturePageResponse,
    CaptureSessionPatch,
    CaptureSessionResponse,
)
from app.services.capture import capture_service

router = APIRouter(prefix="/capture-sessions", tags=["capture"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_capture_session(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaptureSessionResponse:
    session = capture_service.create_session(db, user)
    return CaptureSessionResponse(
        id=session.id,
        owner=session.owner,
        status=session.status,
        revision=session.revision,
        expires_at=session.expires_at,
        pages=[],
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/{session_id}")
def get_capture_session(
    session_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaptureSessionResponse:
    session = (
        db.query(CaptureSession)
        .filter(CaptureSession.id == session_id, CaptureSession.owner == user)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    pages = (
        db.query(CapturePage)
        .filter(CapturePage.session_id == session_id)
        .order_by(CapturePage.page_number)
        .all()
    )

    page_responses = [
        CapturePageResponse(
            id=p.id,
            session_id=p.session_id,
            asset_id=p.asset_id,
            page_number=p.page_number,
            rotation=p.rotation,
            crop_box=p.crop_box,
            upload_status=p.upload_status,
            created_at=p.created_at,
        )
        for p in pages
    ]

    return CaptureSessionResponse(
        id=session.id,
        owner=session.owner,
        status=session.status,
        revision=session.revision,
        expires_at=session.expires_at,
        pages=page_responses,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.put("/{session_id}/pages/{page_id}/file", status_code=status.HTTP_201_CREATED)
async def upload_capture_page_file(
    session_id: str,
    page_id: str,
    request: Request,
    user: CurrentUser,
    page_number: Optional[int] = None,
    filename: Optional[str] = "capture.jpg",
    db: Session = Depends(get_db),
) -> CapturePageResponse:
    try:
        page = capture_service.add_page_file(
            db=db,
            owner=user,
            session_id=session_id,
            file_stream=request.stream(),
            filename=filename or "capture.jpg",
            page_number=page_number,
        )
        return CapturePageResponse.model_validate(page)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{session_id}")
def patch_capture_session(
    session_id: str,
    patch: CaptureSessionPatch,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaptureSessionResponse:
    try:
        session = capture_service.patch_session(
            db=db,
            owner=user,
            session_id=session_id,
            pages_patch=[p.model_dump() for p in patch.pages],
            client_revision=patch.revision,
        )
        return get_capture_session(session_id, user, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{session_id}/finalize", status_code=status.HTTP_202_ACCEPTED)
def finalize_capture_session(
    session_id: str,
    req: CaptureFinalizeRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    try:
        doc = capture_service.finalize_session(
            db=db,
            owner=user,
            session_id=session_id,
            ordered_page_ids=req.ordered_page_ids,
            draft_revision=req.draft_revision,
            title=req.title,
        )
        return {
            "document_id": doc.id,
            "status": "queued",
            "message": "Capture session finalized, PDF assembly and OCR queued",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{session_id}")
def discard_capture_session(
    session_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    session = (
        db.query(CaptureSession)
        .filter(CaptureSession.id == session_id, CaptureSession.owner == user, CaptureSession.status == "draft")
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft session not found")

    session.status = "discarded"
    db.commit()
    return {"message": "Draft capture session discarded"}
