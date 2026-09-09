from __future__ import annotations

import difflib
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.base import utc_now
from app.models.document import Document
from app.models.tag import DocumentTag, DocumentTagOverride, Tag, TagName
from app.models.user import AuditEvent


def normalize_tag_name(name: str) -> str:
    """Normalize string using NFKC, casefold, and collapsed whitespace."""
    if not name:
        return ""
    # Unicode NFKC
    norm = unicodedata.normalize("NFKC", name)
    # Casefold
    folded = norm.casefold()
    # Collapse multiple whitespace
    tokens = folded.split()
    return " ".join(tokens)


DEFAULT_DOCUMENT_TYPES = [
    {"name": "Rechnungen", "aliases": ["Rechnung", "Invoice", "Invoices", "Bill", "Bills"], "color": "#3B82F6"},
    {"name": "Verträge", "aliases": ["Vertrag", "Contract", "Contracts"], "color": "#10B981"},
    {"name": "Belege", "aliases": ["Beleg", "Quittung", "Receipt", "Receipts"], "color": "#F59E0B"},
    {"name": "Versicherungen", "aliases": ["Versicherung", "Insurance"], "color": "#8B5CF6"},
    {"name": "Steuer", "aliases": ["Steuern", "Tax", "Taxes", "Finanzamt"], "color": "#EF4444"},
    {"name": "Bank", "aliases": ["Kontoauszug", "Bank Statement"], "color": "#06B6D4"},
    {"name": "Behörden", "aliases": ["Amt", "Behörde"], "color": "#6B7280"},
    {"name": "Gesundheit", "aliases": ["Arzt", "Rezept", "Medical"], "color": "#EC4899"},
    {"name": "Korrespondenz", "aliases": ["Brief", "Letter"], "color": "#84CC16"},
    {"name": "Anleitungen", "aliases": ["Anleitung", "Manual"], "color": "#14B8A6"},
    {"name": "Garantien", "aliases": ["Garantie", "Warranty"], "color": "#F97316"},
]


class TagService:
    def ensure_default_tags(self, db: Session, owner: str) -> None:
        """Create default document types for a new user if not already existing."""
        existing_canonical = db.query(TagName).filter(
            TagName.owner == owner,
            TagName.is_canonical == True,
        ).first()

        if existing_canonical:
            return

        for doc_type in DEFAULT_DOCUMENT_TYPES:
            tag = Tag(
                owner=owner,
                name=doc_type["name"],
                kind="document_type",
                color=doc_type["color"],
            )
            db.add(tag)
            db.flush()

            # Add canonical name
            db.add(TagName(
                tag_id=tag.id,
                owner=owner,
                name=doc_type["name"],
                normalized_name=normalize_tag_name(doc_type["name"]),
                is_canonical=True,
            ))

            # Add aliases
            for alias in doc_type["aliases"]:
                norm_alias = normalize_tag_name(alias)
                # Check duplicate
                if norm_alias != normalize_tag_name(doc_type["name"]):
                    db.add(TagName(
                        tag_id=tag.id,
                        owner=owner,
                        name=alias,
                        normalized_name=norm_alias,
                        is_canonical=False,
                    ))

        db.commit()

    def resolve_name(self, db: Session, owner: str, raw_name: str) -> Tuple[Optional[Tag], bool, List[Tag]]:
        """
        Resolve a tag name or alias.
        Returns: (resolved_tag_or_none, resolved_existing_bool, similar_tags_list)
        """
        norm_input = normalize_tag_name(raw_name)
        if not norm_input:
            return None, False, []

        # Exact match in canonical names or aliases
        existing_name = (
            db.query(TagName)
            .filter(TagName.owner == owner, TagName.normalized_name == norm_input)
            .first()
        )

        if existing_name:
            tag = db.query(Tag).filter(Tag.id == existing_name.tag_id).first()
            if tag and tag.merged_into_id:
                # Follow redirect if merged
                target_tag = db.query(Tag).filter(Tag.id == tag.merged_into_id).first()
                if target_tag:
                    return target_tag, True, []
            return tag, True, []

        # Find similar tags by string similarity on all known names/aliases
        all_names = db.query(TagName).filter(TagName.owner == owner).all()
        name_map = {n.normalized_name: n.tag_id for n in all_names}
        similar_keys = difflib.get_close_matches(norm_input, list(name_map.keys()), n=5, cutoff=0.6)

        similar_tags: List[Tag] = []
        seen_ids = set()
        for key in similar_keys:
            t_id = name_map[key]
            if t_id not in seen_ids:
                seen_ids.add(t_id)
                tag = db.query(Tag).filter(Tag.id == t_id, Tag.merged_into_id.is_(None)).first()
                if tag:
                    similar_tags.append(tag)

        return None, False, similar_tags

    def create_tag(
        self,
        db: Session,
        owner: str,
        name: str,
        kind: str = "topic",
        color: Optional[str] = None,
    ) -> Tag:
        """Create a new canonical tag."""
        norm_name = normalize_tag_name(name)
        existing_name = (
            db.query(TagName)
            .filter(TagName.owner == owner, TagName.normalized_name == norm_name)
            .first()
        )
        if existing_name:
            existing_tag = db.query(Tag).filter(Tag.id == existing_name.tag_id).first()
            if existing_tag:
                return existing_tag

        tag = Tag(
            owner=owner,
            name=name.strip(),
            kind=kind,
            color=color,
        )
        db.add(tag)
        db.flush()

        tag_name = TagName(
            tag_id=tag.id,
            owner=owner,
            name=name.strip(),
            normalized_name=norm_name,
            is_canonical=True,
        )
        db.add(tag_name)
        db.commit()
        return tag

    def add_alias(self, db: Session, owner: str, tag_id: str, alias: str) -> TagName:
        """Add an alias to an existing tag."""
        tag = db.query(Tag).filter(Tag.id == tag_id, Tag.owner == owner).first()
        if not tag:
            raise ValueError("Tag not found.")

        norm_alias = normalize_tag_name(alias)
        existing = (
            db.query(TagName)
            .filter(TagName.owner == owner, TagName.normalized_name == norm_alias)
            .first()
        )
        if existing:
            if existing.tag_id == tag_id:
                return existing
            raise ValueError(f"Name '{alias}' is already used by another tag.")

        tag_name = TagName(
            tag_id=tag.id,
            owner=owner,
            name=alias.strip(),
            normalized_name=norm_alias,
            is_canonical=False,
        )
        db.add(tag_name)
        db.commit()
        return tag_name

    def merge_tags(self, db: Session, owner: str, source_tag_id: str, target_tag_id: str) -> Tag:
        """
        Merge source_tag into target_tag.
        Reassigns all document relationships without duplicates, reassigns aliases,
        and sets merged_into_id on source tag.
        """
        if source_tag_id == target_tag_id:
            raise ValueError("Cannot merge tag into itself.")

        source_tag = db.query(Tag).filter(Tag.id == source_tag_id, Tag.owner == owner).first()
        target_tag = db.query(Tag).filter(Tag.id == target_tag_id, Tag.owner == owner).first()

        if not source_tag or not target_tag:
            raise ValueError("Source or target tag not found.")

        # Reassign document tags
        source_doc_tags = db.query(DocumentTag).filter(DocumentTag.tag_id == source_tag_id).all()
        for sdt in source_doc_tags:
            existing_target = (
                db.query(DocumentTag)
                .filter(
                    DocumentTag.document_id == sdt.document_id,
                    DocumentTag.tag_id == target_tag_id,
                )
                .first()
            )
            if not existing_target:
                sdt.tag_id = target_tag_id
            else:
                db.delete(sdt)

        # Reassign aliases: source canonical name becomes alias of target
        source_aliases = db.query(TagName).filter(TagName.tag_id == source_tag_id).all()
        for sa in source_aliases:
            sa.tag_id = target_tag_id
            sa.is_canonical = False

        # Mark source as merged
        source_tag.merged_into_id = target_tag_id

        # Log audit event
        audit = AuditEvent(
            owner=owner,
            action="tag_merge",
            entity_type="tag",
            entity_id=source_tag_id,
            details={"target_tag_id": target_tag_id, "source_name": source_tag.name, "target_name": target_tag.name},
        )
        db.add(audit)
        db.commit()
        return target_tag

    def delete_tag(self, db: Session, owner: str, tag_id: str) -> int:
        """
        Delete a tag. Documents are NOT deleted.
        If a document loses its only accepted tag, its classification_state reverts to 'needs_review'.
        """
        tag = db.query(Tag).filter(Tag.id == tag_id, Tag.owner == owner).first()
        if not tag:
            raise ValueError("Tag not found.")

        # Find affected documents
        affected_doc_ids = [
            dt.document_id
            for dt in db.query(DocumentTag.document_id).filter(DocumentTag.tag_id == tag_id).all()
        ]

        # Delete tag associations
        db.query(DocumentTag).filter(DocumentTag.tag_id == tag_id).delete(synchronize_session=False)
        db.query(DocumentTagOverride).filter(DocumentTagOverride.tag_id == tag_id).delete(synchronize_session=False)
        db.query(TagName).filter(TagName.tag_id == tag_id).delete(synchronize_session=False)
        db.delete(tag)
        db.flush()

        # Check affected documents
        for doc_id in affected_doc_ids:
            remaining_tags_count = (
                db.query(func.count(DocumentTag.id))
                .filter(DocumentTag.document_id == doc_id)
                .scalar()
            )
            if remaining_tags_count == 0:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if doc and doc.classification_state == "classified":
                    doc.classification_state = "needs_review"

        db.commit()
        return len(affected_doc_ids)


tag_service = TagService()
