from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.document import Document
from app.models.tag import DocumentTag, DocumentTagOverride, Tag, TagName
from app.schemas.tag import (
    TagAliasCreate,
    TagCreate,
    TagMergeRequest,
    TagNameResponse,
    TagResolveResponse,
    TagResponse,
    TagUpdate,
)
from app.services.tags import normalize_tag_name, tag_service

router = APIRouter(tags=["tags"])


@router.get("/tags")
def list_tags(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> List[TagResponse]:
    tags = db.query(Tag).filter(Tag.owner == user, Tag.merged_into_id.is_(None)).all()
    results = []
    for t in tags:
        # Fetch aliases
        aliases = [
            a.name
            for a in db.query(TagName).filter(TagName.tag_id == t.id, TagName.is_canonical == False).all()
        ]
        # Count documents
        doc_count = db.query(func.count(DocumentTag.id)).filter(DocumentTag.tag_id == t.id).scalar() or 0
        results.append(
            TagResponse(
                id=t.id,
                owner=t.owner,
                name=t.name,
                kind=t.kind,
                color=t.color,
                merged_into_id=t.merged_into_id,
                aliases=aliases,
                document_count=doc_count,
                created_at=t.created_at,
            )
        )
    return results


@router.post("/tags")
def create_or_resolve_tag(
    req: TagCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> TagResolveResponse:
    """Resolve input name against canonical tags & aliases; returns existing if matched, or creates."""
    resolved_tag, exists, similar = tag_service.resolve_name(db, user, req.name)
    if exists and resolved_tag:
        return TagResolveResponse(
            resolved_existing=True,
            tag_id=resolved_tag.id,
            name=resolved_tag.name,
            similar_tags=[],
        )

    # If not resolved and no similar tags or client explicitly requested creation
    created = tag_service.create_tag(db, user, req.name, kind=req.kind, color=req.color)
    similar_responses = [
        TagResponse(
            id=s.id,
            owner=s.owner,
            name=s.name,
            kind=s.kind,
            color=s.color,
            aliases=[],
            document_count=0,
            created_at=s.created_at,
        )
        for s in similar
    ]
    return TagResolveResponse(
        resolved_existing=False,
        tag_id=created.id,
        name=created.name,
        similar_tags=similar_responses,
    )


@router.patch("/tags/{tag_id}")
def update_tag(
    tag_id: str,
    update: TagUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> TagResponse:
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.owner == user).first()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    if update.name is not None:
        tag.name = update.name.strip()
        canonical_name = (
            db.query(TagName)
            .filter(TagName.tag_id == tag.id, TagName.is_canonical == True)
            .first()
        )
        if canonical_name:
            canonical_name.name = update.name.strip()
            canonical_name.normalized_name = normalize_tag_name(update.name)

    if update.kind is not None:
        tag.kind = update.kind
    if update.color is not None:
        tag.color = update.color

    db.commit()
    return TagResponse(
        id=tag.id,
        owner=tag.owner,
        name=tag.name,
        kind=tag.kind,
        color=tag.color,
        aliases=[],
        document_count=0,
        created_at=tag.created_at,
    )


@router.delete("/tags/{tag_id}")
def delete_tag(
    tag_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    try:
        affected_count = tag_service.delete_tag(db, user, tag_id)
        return {"message": "Tag deleted", "affected_documents_count": affected_count}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/tags/{tag_id}/aliases")
def add_tag_alias(
    tag_id: str,
    req: TagAliasCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> TagNameResponse:
    try:
        alias = tag_service.add_alias(db, user, tag_id, req.name)
        return TagNameResponse.model_validate(alias)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/tags/{tag_id}/merge")
def merge_tag(
    tag_id: str,
    req: TagMergeRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    try:
        target = tag_service.merge_tags(db, user, tag_id, req.target_tag_id)
        return {"message": "Tags merged successfully", "target_tag_id": target.id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/documents/{document_id}/tags/{tag_id}")
def assign_tag_to_document(
    document_id: str,
    tag_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    doc = db.query(Document).filter(Document.id == document_id, Document.owner == user).first()
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.owner == user).first()
    if not doc or not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document or Tag not found")

    existing = (
        db.query(DocumentTag)
        .filter(DocumentTag.document_id == document_id, DocumentTag.tag_id == tag_id)
        .first()
    )
    if not existing:
        db.add(DocumentTag(document_id=document_id, tag_id=tag_id, source="manual", score=1.0))

    # Mark manual override
    override = (
        db.query(DocumentTagOverride)
        .filter(DocumentTagOverride.document_id == document_id, DocumentTagOverride.tag_id == tag_id)
        .first()
    )
    if not override:
        db.add(DocumentTagOverride(document_id=document_id, tag_id=tag_id, state="confirmed", owner=user))
    else:
        override.state = "confirmed"

    db.commit()
    from app.services.search import search_service
    search_service.update_document_index(db, doc.id, user)
    return {"message": "Tag assigned to document"}


@router.delete("/documents/{document_id}/tags/{tag_id}")
def remove_tag_from_document(
    document_id: str,
    tag_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    db.query(DocumentTag).filter(DocumentTag.document_id == document_id, DocumentTag.tag_id == tag_id).delete()

    # Record manual exclusion override
    override = (
        db.query(DocumentTagOverride)
        .filter(DocumentTagOverride.document_id == document_id, DocumentTagOverride.tag_id == tag_id)
        .first()
    )
    if not override:
        db.add(DocumentTagOverride(document_id=document_id, tag_id=tag_id, state="excluded", owner=user))
    else:
        override.state = "excluded"

    db.commit()
    from app.services.search import search_service
    search_service.update_document_index(db, document_id, user)
    return {"message": "Tag removed from document"}
