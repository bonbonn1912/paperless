from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.base import utc_now
from app.models.document import Document, DocumentAsset, DocumentFieldOverride, DocumentPage
from app.models.folder import DocumentFolder, Folder
from app.models.job import Job, JobEvent
from app.models.tag import DocumentTag, Tag
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentPatch,
    DocumentResponse,
)
from app.schemas.folder import FolderResponse
from app.schemas.tag import TagResponse
from app.services.search import search_service
from app.services.storage import DuplicateDocumentError, StorageError, storage_service

router = APIRouter(prefix="/documents", tags=["documents"])


def _format_doc_response(db: Session, doc: Document) -> DocumentResponse:
    # Fetch tags
    doc_tags = (
        db.query(Tag)
        .join(DocumentTag, DocumentTag.tag_id == Tag.id)
        .filter(DocumentTag.document_id == doc.id)
        .all()
    )
    tag_responses = [
        TagResponse(
            id=t.id,
            owner=t.owner,
            name=t.name,
            kind=t.kind,
            color=t.color,
            merged_into_id=t.merged_into_id,
            created_at=t.created_at,
        )
        for t in doc_tags
    ]

    # Fetch folders
    doc_folders = (
        db.query(Folder)
        .join(DocumentFolder, DocumentFolder.folder_id == Folder.id)
        .filter(DocumentFolder.document_id == doc.id)
        .all()
    )
    folder_responses = [
        FolderResponse(
            id=f.id,
            owner=f.owner,
            name=f.name,
            parent_id=f.parent_id,
            created_at=f.created_at,
        )
        for f in doc_folders
    ]

    amount_dec = f"{doc.amount / 100:.2f}" if doc.amount is not None else None

    return DocumentResponse(
        id=doc.id,
        owner=doc.owner,
        original_name=doc.original_name,
        storage_key=doc.storage_key,
        mime_type=doc.mime_type,
        file_size=doc.file_size,
        sha256=doc.sha256,
        title=doc.title,
        sender=doc.sender,
        document_date=doc.document_date,
        due_date=doc.due_date,
        amount=doc.amount,
        amount_decimal=amount_dec,
        currency=doc.currency,
        source=doc.source,
        metadata_revision=doc.metadata_revision,
        processing_state=doc.processing_state,
        classification_state=doc.classification_state,
        index_state=doc.index_state,
        tags=tag_responses,
        folders=folder_responses,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def upload_single_document(
    user: CurrentUser,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Upload a single file, stream to staging, save permanently, and enqueue base pipeline."""
    try:
        doc_uuid, storage_key, file_size, sha256_hash, mime_type = storage_service.save_upload_stream(
            db=db,
            owner=user,
            stream=file.file,
            original_filename=file.filename or "upload.pdf",
            content_length=file.size,
        )
    except DuplicateDocumentError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "document_already_exists", "existing_id": e.existing_document_id},
        )
    except StorageError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Create document
    doc = Document(
        id=doc_uuid,
        owner=user,
        original_name=file.filename or "upload.pdf",
        storage_key=storage_key,
        mime_type=mime_type,
        file_size=file_size,
        sha256=sha256_hash,
        title=file.filename,
        source="upload",
        processing_state="queued",
        classification_state="pending",
        index_state="pending",
    )
    db.add(doc)
    db.flush()

    # Create job
    run_id = str(uuid.uuid4())
    job = Job(
        owner=user,
        document_id=doc.id,
        run_id=run_id,
        job_type="base_pipeline",
        state="queued",
        step="queued",
        priority=10,
    )
    db.add(job)
    db.flush()

    db.add(JobEvent(
        job_id=job.id,
        from_state="none",
        to_state="queued",
        step="queued",
        reason="Uploaded file queued for processing",
    ))

    doc.active_run_id = run_id
    db.commit()

    return {
        "document_id": doc.id,
        "job_id": job.id,
        "status": "queued",
        "message": "File accepted and processing queued",
    }


@router.get("")
def list_documents(
    user: CurrentUser,
    q: Optional[str] = None,
    folder_id: Optional[str] = None,
    include_descendants: bool = True,
    tag_ids: Optional[List[str]] = Query(None),
    tag_mode: str = "any",
    classification_state: Optional[str] = None,
    processing_state: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """List documents with global FTS5 search and faceted filters."""
    docs, total_count, snippets = search_service.search_documents(
        db=db,
        owner=user,
        query=q,
        tag_ids=tag_ids,
        tag_mode=tag_mode,
        folder_id=folder_id,
        include_descendants=include_descendants,
        classification_state=classification_state,
        processing_state=processing_state,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )

    items = [_format_doc_response(db, d) for d in docs]
    return {
        "items": items,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "snippets": snippets,
    }


@router.get("/{document_id}")
def get_document_details(
    document_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> DocumentDetailResponse:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner == user, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    base_resp = _format_doc_response(db, doc)

    # Pages
    pages = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
        .all()
    )
    # Assets
    assets = (
        db.query(DocumentAsset)
        .filter(DocumentAsset.document_id == document_id)
        .order_by(DocumentAsset.created_at)
        .all()
    )
    # Overrides
    overrides = (
        db.query(DocumentFieldOverride)
        .filter(DocumentFieldOverride.document_id == document_id)
        .all()
    )

    return DocumentDetailResponse(
        **base_resp.model_dump(),
        pages=[p for p in pages],
        assets=[a for a in assets],
        field_overrides={o.field_name: o.value for o in overrides},
        active_job_id=doc.active_run_id,
    )


@router.patch("/{document_id}")
def update_document(
    document_id: str,
    patch: DocumentPatch,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner == user, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if patch.title is not None:
        doc.title = patch.title
        _set_field_override(db, doc.id, "title", patch.title, user)
    if patch.sender is not None:
        doc.sender = patch.sender
        _set_field_override(db, doc.id, "sender", patch.sender, user)
    if patch.document_date is not None:
        doc.document_date = patch.document_date
        _set_field_override(db, doc.id, "document_date", patch.document_date.isoformat(), user)
    if patch.due_date is not None:
        doc.due_date = patch.due_date
        _set_field_override(db, doc.id, "due_date", patch.due_date.isoformat(), user)
    if patch.amount_decimal is not None:
        try:
            val = float(patch.amount_decimal.replace(",", "."))
            cents = int(round(val * 100))
            doc.amount = cents
            _set_field_override(db, doc.id, "amount", str(cents), user)
        except ValueError:
            pass
    if patch.currency is not None:
        doc.currency = patch.currency

    doc.metadata_revision += 1
    db.commit()
    # Update search index with new metadata
    search_service.update_document_index(db, doc.id, user)
    return _format_doc_response(db, doc)


def _set_field_override(db: Session, doc_id: str, field_name: str, value: str, owner: str) -> None:
    existing = (
        db.query(DocumentFieldOverride)
        .filter(DocumentFieldOverride.document_id == doc_id, DocumentFieldOverride.field_name == field_name)
        .first()
    )
    if existing:
        existing.value = value
    else:
        db.add(DocumentFieldOverride(
            document_id=doc_id,
            field_name=field_name,
            value=value,
            owner=owner,
        ))


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner == user, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc.deleted_at = utc_now()
    db.commit()

    # Remove from search index
    search_service.update_document_index(db, doc.id, user)
    return {"message": "Document marked as deleted"}


@router.post("/{document_id}/reprocess")
def reprocess_document(
    document_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner == user, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    run_id = str(uuid.uuid4())
    job = Job(
        owner=user,
        document_id=doc.id,
        run_id=run_id,
        job_type="base_pipeline",
        state="queued",
        step="queued",
        priority=8,  # manual retry priority
    )
    db.add(job)
    doc.active_run_id = run_id
    doc.processing_state = "queued"
    db.commit()

    return {"job_id": job.id, "run_id": run_id, "status": "queued"}
