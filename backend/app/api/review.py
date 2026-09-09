from __future__ import annotations

import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.classification import ClassificationRule
from app.models.document import Document, DocumentFieldOverride
from app.models.tag import DocumentTag, DocumentTagOverride, Tag
from app.schemas.review import (
    BulkReviewRequest,
    BulkReviewResponse,
    BulkReviewResultItem,
    ReviewConfirmRequest,
)
from app.services.search import search_service

router = APIRouter(prefix="/documents", tags=["review"])


@router.post("/{document_id}/review")
def review_document(
    document_id: str,
    req: ReviewConfirmRequest,
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

    # 1. Apply confirmed tags
    for tid in req.tag_ids:
        tag = db.query(Tag).filter(Tag.id == tid, Tag.owner == user).first()
        if tag:
            # Upsert DocumentTag
            existing_dt = db.query(DocumentTag).filter(DocumentTag.document_id == doc.id, DocumentTag.tag_id == tid).first()
            if not existing_dt:
                db.add(DocumentTag(document_id=doc.id, tag_id=tid, source="manual", score=1.0))
            else:
                existing_dt.source = "manual"
                existing_dt.score = 1.0

            # Override
            ov = db.query(DocumentTagOverride).filter(DocumentTagOverride.document_id == doc.id, DocumentTagOverride.tag_id == tid).first()
            if not ov:
                db.add(DocumentTagOverride(document_id=doc.id, tag_id=tid, state="confirmed", owner=user))
            else:
                ov.state = "confirmed"

    # 2. Apply excluded tags
    for tid in req.excluded_tag_ids:
        db.query(DocumentTag).filter(DocumentTag.document_id == doc.id, DocumentTag.tag_id == tid).delete()
        ov = db.query(DocumentTagOverride).filter(DocumentTagOverride.document_id == doc.id, DocumentTagOverride.tag_id == tid).first()
        if not ov:
            db.add(DocumentTagOverride(document_id=doc.id, tag_id=tid, state="excluded", owner=user))
        else:
            ov.state = "excluded"

    # 3. Apply field overrides
    for field_name, val in req.field_overrides.items():
        existing_fo = db.query(DocumentFieldOverride).filter(DocumentFieldOverride.document_id == doc.id, DocumentFieldOverride.field_name == field_name).first()
        if not existing_fo:
            db.add(DocumentFieldOverride(document_id=doc.id, field_name=field_name, value=str(val) if val is not None else None, owner=user))
        else:
            existing_fo.value = str(val) if val is not None else None

        # Update doc direct field if matched
        if field_name == "title":
            doc.title = val
        elif field_name == "sender":
            doc.sender = val
        elif field_name == "amount" and val is not None:
            try:
                doc.amount = int(val)
            except ValueError:
                pass
        elif field_name == "currency":
            doc.currency = val

    # 4. Update classification state
    if req.mark_as_reviewed:
        doc.classification_state = "classified"

    # 5. Optionally create rule
    if req.create_rule and req.tag_ids and doc.sender:
        rule_name = req.rule_name or f"Regel für {doc.sender}"
        db.add(ClassificationRule(
            owner=user,
            name=rule_name,
            conditions={"all": [{"field": "sender", "contains": doc.sender}]},
            target_tag_ids=req.tag_ids,
            priority=10,
        ))

    doc.metadata_revision += 1
    db.commit()

    search_service.update_document_index(db, doc.id, user)
    return {
        "document_id": doc.id,
        "classification_state": doc.classification_state,
        "message": "Review decision saved successfully",
    }


@router.post("/bulk-review")
def bulk_review_documents(
    req: BulkReviewRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> BulkReviewResponse:
    results: List[BulkReviewResultItem] = []

    for doc_id in req.document_ids:
        doc = db.query(Document).filter(Document.id == doc_id, Document.owner == user, Document.deleted_at.is_(None)).first()
        if not doc:
            results.append(BulkReviewResultItem(document_id=doc_id, success=False, error="Document not found"))
            continue

        try:
            # Add tags
            for tid in req.add_tag_ids:
                if not db.query(DocumentTag).filter(DocumentTag.document_id == doc.id, DocumentTag.tag_id == tid).first():
                    db.add(DocumentTag(document_id=doc.id, tag_id=tid, source="manual", score=1.0))
                # Set override
                ov = db.query(DocumentTagOverride).filter(DocumentTagOverride.document_id == doc.id, DocumentTagOverride.tag_id == tid).first()
                if not ov:
                    db.add(DocumentTagOverride(document_id=doc.id, tag_id=tid, state="confirmed", owner=user))
                else:
                    ov.state = "confirmed"

            # Remove tags
            for tid in req.remove_tag_ids:
                db.query(DocumentTag).filter(DocumentTag.document_id == doc.id, DocumentTag.tag_id == tid).delete()
                ov = db.query(DocumentTagOverride).filter(DocumentTagOverride.document_id == doc.id, DocumentTagOverride.tag_id == tid).first()
                if not ov:
                    db.add(DocumentTagOverride(document_id=doc.id, tag_id=tid, state="excluded", owner=user))
                else:
                    ov.state = "excluded"

            if req.mark_as_reviewed:
                doc.classification_state = "classified"

            doc.metadata_revision += 1
            db.commit()
            search_service.update_document_index(db, doc.id, user)
            results.append(BulkReviewResultItem(document_id=doc.id, success=True))
        except Exception as e:
            results.append(BulkReviewResultItem(document_id=doc_id, success=False, error=str(e)))

    return BulkReviewResponse(results=results)
