from __future__ import annotations

import hashlib
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.config import settings
from app.db.session import get_db
from app.models.batch import UploadBatch, UploadItem
from app.models.classification import ClassificationResult
from app.models.document import Document
from app.models.job import Job
from app.schemas.job import (
    BatchStatusSummary,
    JobSummary,
    StatusItemSummary,
    StatusPollRequest,
    StatusPollResponse,
)

router = APIRouter(prefix="/processing", tags=["processing"])


@router.post("/status")
def get_processing_status(
    req: StatusPollRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> StatusPollResponse:
    """Centralized bulk status polling endpoint for batches and documents."""
    if len(req.batch_ids) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exceeded limit of maximum 10 batch_ids per status request",
        )

    # 1. Fetch batches
    batches: List[UploadBatch] = []
    if req.batch_ids:
        batches = (
            db.query(UploadBatch)
            .filter(UploadBatch.id.in_(req.batch_ids), UploadBatch.owner == user)
            .all()
        )

    # 2. Fetch all items from batches
    batch_items: List[UploadItem] = []
    if batches:
        b_ids = [b.id for b in batches]
        batch_items = (
            db.query(UploadItem)
            .filter(UploadItem.batch_id.in_(b_ids))
            .order_by(UploadItem.position)
            .all()
        )

    # Collect document IDs
    doc_ids_to_fetch = set(req.document_ids)
    for bi in batch_items:
        if bi.document_id:
            doc_ids_to_fetch.add(bi.document_id)

    total_target_count = len(batch_items) + len(req.document_ids)
    if total_target_count > settings.STATUS_MAX_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exceeded maximum items limit of {settings.STATUS_MAX_ITEMS}",
        )

    # 3. Fetch documents
    docs: Dict[str, Document] = {}
    if doc_ids_to_fetch:
        docs_list = (
            db.query(Document)
            .filter(Document.id.in_(doc_ids_to_fetch), Document.owner == user)
            .all()
        )
        docs = {d.id: d for d in docs_list}

    # 4. Fetch jobs for documents
    jobs: Dict[str, Job] = {}
    if doc_ids_to_fetch:
        jobs_list = (
            db.query(Job)
            .filter(Job.document_id.in_(doc_ids_to_fetch), Job.owner == user)
            .order_by(Job.created_at.desc())
            .all()
        )
        for j in jobs_list:
            if j.document_id and j.document_id not in jobs:
                jobs[j.document_id] = j

    # 5. Fetch review reasons from classification_results
    review_reasons_map: Dict[str, List[str]] = {}
    if doc_ids_to_fetch:
        cls_results = (
            db.query(ClassificationResult)
            .filter(ClassificationResult.document_id.in_(doc_ids_to_fetch))
            .order_by(ClassificationResult.created_at.desc())
            .all()
        )
        for cr in cls_results:
            if cr.document_id not in review_reasons_map:
                review_reasons_map[cr.document_id] = cr.review_reasons or []

    # 6. Build item summaries
    items_summary: List[StatusItemSummary] = []
    hasher = hashlib.sha256()

    # Add items from batches
    for bi in batch_items:
        doc = docs.get(bi.document_id) if bi.document_id else None
        job = jobs.get(bi.document_id) if bi.document_id else None

        job_sum = None
        if job:
            prog = job.progress or {}
            job_sum = JobSummary(
                id=job.id,
                state=job.state,
                step=job.step,
                processed_pages=prog.get("processed_pages", 0),
                total_pages=prog.get("total_pages", 0),
                attempt=job.attempts,
                updated_at=job.updated_at,
                next_run_at=job.not_before,
                error_code=job.error_code,
            )

        rev_reasons = review_reasons_map.get(bi.document_id, []) if bi.document_id else []

        status_item = StatusItemSummary(
            batch_id=bi.batch_id,
            item_id=bi.id,
            document_id=bi.document_id,
            upload_state=bi.status,
            processing_state=doc.processing_state if doc else None,
            classification_state=doc.classification_state if doc else None,
            index_state=doc.index_state if doc else None,
            review_reasons=rev_reasons,
            retryable=bool(job and job.state in ("failed", "cancelled")),
            job=job_sum,
        )
        items_summary.append(status_item)

        # Hash entry for revision comparison
        hasher.update(f"{bi.id}:{bi.status}:{bi.updated_at.isoformat()}".encode())
        if doc:
            hasher.update(f"{doc.id}:{doc.processing_state}:{doc.classification_state}:{doc.updated_at.isoformat()}".encode())
        if job:
            hasher.update(f"{job.id}:{job.state}:{job.step}:{job.updated_at.isoformat()}".encode())

    # Add standalone requested document IDs not in any batch
    batch_doc_ids = {bi.document_id for bi in batch_items if bi.document_id}
    for did in req.document_ids:
        if did not in batch_doc_ids and did in docs:
            doc = docs[did]
            job = jobs.get(did)
            job_sum = None
            if job:
                prog = job.progress or {}
                job_sum = JobSummary(
                    id=job.id,
                    state=job.state,
                    step=job.step,
                    processed_pages=prog.get("processed_pages", 0),
                    total_pages=prog.get("total_pages", 0),
                    attempt=job.attempts,
                    updated_at=job.updated_at,
                    next_run_at=job.not_before,
                    error_code=job.error_code,
                )

            status_item = StatusItemSummary(
                document_id=doc.id,
                upload_state="accepted",
                processing_state=doc.processing_state,
                classification_state=doc.classification_state,
                index_state=doc.index_state,
                review_reasons=review_reasons_map.get(did, []),
                retryable=bool(job and job.state in ("failed", "cancelled")),
                job=job_sum,
            )
            items_summary.append(status_item)
            hasher.update(f"{doc.id}:{doc.processing_state}:{doc.classification_state}:{doc.updated_at.isoformat()}".encode())

    current_revision = hasher.hexdigest()

    # Check if unchanged
    if req.known_revision and req.known_revision == current_revision:
        return StatusPollResponse(
            revision=current_revision,
            unchanged=True,
            batches=[],
            items=[],
            poll_after_ms=2000,
        )

    # 7. Build disjunctive batch status summaries
    batch_summaries: List[BatchStatusSummary] = []
    for b in batches:
        b_items = [it for it in items_summary if it.batch_id == b.id]
        total = b.total_items
        uploaded = sum(1 for it in b_items if it.upload_state == "accepted")
        upload_failed = sum(1 for it in b_items if it.upload_state == "failed")
        waiting = sum(1 for it in b_items if it.upload_state == "waiting_for_upload")

        ready = sum(1 for it in b_items if it.processing_state == "ready" and it.classification_state == "classified")
        needs_review = sum(1 for it in b_items if it.classification_state == "needs_review")
        processing = sum(1 for it in b_items if it.processing_state == "processing")
        queued = sum(1 for it in b_items if it.processing_state == "queued")
        failed = sum(1 for it in b_items if it.processing_state == "failed")
        cancelled = sum(1 for it in b_items if it.job and it.job.state == "cancelled")

        terminal = all(
            it.upload_state in ("failed", "skipped")
            or (it.processing_state in ("ready", "failed") and it.classification_state in ("classified", "needs_review"))
            for it in b_items
        ) if b_items else False

        batch_summaries.append(
            BatchStatusSummary(
                batch_id=b.id,
                total=total,
                uploaded=uploaded,
                upload_failed=upload_failed,
                waiting_for_upload=waiting,
                ready=ready,
                needs_review=needs_review,
                processing=processing,
                queued=queued,
                failed=failed,
                cancelled=cancelled,
                terminal=terminal,
            )
        )

    return StatusPollResponse(
        revision=current_revision,
        unchanged=False,
        batches=batch_summaries,
        items=items_summary,
        poll_after_ms=2000,
    )
