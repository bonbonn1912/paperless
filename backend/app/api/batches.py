from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.config import settings
from app.db.session import get_db
from app.models.batch import UploadBatch, UploadItem
from app.models.document import Document
from app.models.job import Job, JobEvent
from app.schemas.batch import (
    BatchCreateRequest,
    BatchCreateResponse,
    BatchResponse,
    UploadItemResponse,
)
from app.services.storage import DuplicateDocumentError, StorageError, storage_service

router = APIRouter(prefix="/upload-batches", tags=["batches"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_upload_batch(
    req: BatchCreateRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> BatchCreateResponse:
    if len(req.items) > settings.MAX_BATCH_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch exceeds maximum limit of {settings.MAX_BATCH_FILES} files.",
        )

    batch_id = str(uuid.uuid4())
    batch = UploadBatch(
        id=batch_id,
        owner=user,
        total_items=len(req.items),
        status="in_progress",
    )
    db.add(batch)
    db.flush()

    item_id_map = {}
    for idx, item in enumerate(req.items):
        item_id = str(uuid.uuid4())
        up_item = UploadItem(
            id=item_id,
            batch_id=batch_id,
            client_item_id=item.client_item_id,
            position=item.position or idx,
            original_name=item.original_name,
            file_size=item.file_size,
            mime_type=item.mime_type,
            status="waiting_for_upload",
        )
        db.add(up_item)
        item_id_map[item.client_item_id] = item_id

    db.commit()
    return BatchCreateResponse(
        batch_id=batch_id,
        total_items=len(req.items),
        max_batch_files=settings.MAX_BATCH_FILES,
        upload_concurrency=settings.UPLOAD_CONCURRENCY,
        item_ids=item_id_map,
    )


@router.get("/{batch_id}")
def get_batch(
    batch_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> BatchResponse:
    batch = (
        db.query(UploadBatch)
        .filter(UploadBatch.id == batch_id, UploadBatch.owner == user)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    items = (
        db.query(UploadItem)
        .filter(UploadItem.batch_id == batch_id)
        .order_by(UploadItem.position)
        .all()
    )

    return BatchResponse(
        id=batch.id,
        owner=batch.owner,
        total_items=batch.total_items,
        status=batch.status,
        items=[UploadItemResponse.model_validate(it) for it in items],
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


@router.put("/{batch_id}/items/{item_id}/file", status_code=status.HTTP_202_ACCEPTED)
async def upload_batch_item_file(
    batch_id: str,
    item_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> dict:
    """Stream file upload for an individual batch item, then immediately enqueue processing."""
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id, UploadBatch.owner == user).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    item = db.query(UploadItem).filter(UploadItem.id == item_id, UploadItem.batch_id == batch_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch item not found")

    # Idempotent re-check
    if item.status == "accepted" and item.document_id and idempotency_key and item.idempotency_key == idempotency_key:
        return {
            "item_id": item.id,
            "document_id": item.document_id,
            "job_id": item.job_id,
            "status": "accepted",
            "message": "Item already uploaded and queued (idempotent replay)",
        }

    item.status = "uploading"
    item.idempotency_key = idempotency_key
    db.commit()

    # Stream request body to staging
    try:
        doc_uuid, storage_key, file_size, sha256_hash, mime_type = await storage_service.save_async_stream(
            db=db,
            owner=user,
            stream_gen=request.stream(),
            original_filename=item.original_name,
        )
    except DuplicateDocumentError as e:
        item.status = "accepted"
        item.document_id = e.existing_document_id
        item.error_code = "duplicate"
        item.error_message = f"Exact duplicate of document {e.existing_document_id}"
        db.commit()
        return {
            "item_id": item.id,
            "document_id": e.existing_document_id,
            "status": "accepted",
            "is_duplicate": True,
            "message": "File is an exact duplicate of an existing document",
        }
    except StorageError as e:
        item.status = "failed"
        item.error_code = "storage_error"
        item.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        item.status = "failed"
        item.error_code = "upload_failed"
        item.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Upload failed: {e}")

    # Create document
    doc = Document(
        id=doc_uuid,
        owner=user,
        original_name=item.original_name,
        storage_key=storage_key,
        mime_type=mime_type,
        file_size=file_size,
        sha256=sha256_hash,
        title=item.original_name,
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
        reason="Batch item upload accepted and queued",
    ))

    doc.active_run_id = run_id
    item.document_id = doc.id
    item.job_id = job.id
    item.status = "accepted"
    db.commit()

    return {
        "item_id": item.id,
        "document_id": doc.id,
        "job_id": job.id,
        "status": "accepted",
        "message": "File accepted and queued for sequential processing",
    }


@router.patch("/{batch_id}/items/{item_id}")
def update_batch_item(
    batch_id: str,
    item_id: str,
    action: str,  # e.g. "skip"
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    item = (
        db.query(UploadItem)
        .join(UploadBatch, UploadBatch.id == UploadItem.batch_id)
        .filter(UploadItem.id == item_id, UploadItem.batch_id == batch_id, UploadBatch.owner == user)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    if action == "skip":
        item.status = "skipped"
        db.commit()
        return {"item_id": item.id, "status": "skipped"}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown action '{action}'")
