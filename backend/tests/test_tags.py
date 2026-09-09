from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.tag import DocumentTag, Tag, TagName
from app.services.tags import normalize_tag_name, tag_service


def test_normalize_tag_name():
    assert normalize_tag_name("  Rechnung  ") == "rechnung"
    assert normalize_tag_name("RECHNUNGEN") == "rechnungen"
    assert normalize_tag_name("Multiple   Spaces\tHere") == "multiple spaces here"
    assert normalize_tag_name("Café") == "café"


def test_alias_resolution(db_session: Session):
    tag_service.ensure_default_tags(db_session, "user1")

    # "Invoice" must resolve to canonical tag "Rechnungen"
    resolved_tag, exists, _ = tag_service.resolve_name(db_session, "user1", "Invoice")
    assert exists is True
    assert resolved_tag is not None
    assert resolved_tag.name == "Rechnungen"

    # "invoices" casefold match
    resolved_tag2, exists2, _ = tag_service.resolve_name(db_session, "user1", "invoices")
    assert exists2 is True
    assert resolved_tag2.id == resolved_tag.id

    # Unknown tag
    unknown_tag, exists_unknown, similar = tag_service.resolve_name(db_session, "user1", "Unbekannt123")
    assert exists_unknown is False
    assert unknown_tag is None


def test_tag_merge(db_session: Session):
    tag1 = tag_service.create_tag(db_session, "user1", "Tag Eins")
    tag2 = tag_service.create_tag(db_session, "user1", "Tag Zwei")

    # Associate document with tag1
    doc = Document(
        id="doc-merge-1",
        owner="user1",
        original_name="test.pdf",
        storage_key="test.pdf",
        mime_type="application/pdf",
        file_size=100,
        sha256="sha-merge-1",
    )
    db_session.add(doc)
    db_session.add(DocumentTag(document_id=doc.id, tag_id=tag1.id, source="manual"))
    db_session.commit()

    # Merge tag1 into tag2
    target = tag_service.merge_tags(db_session, "user1", tag1.id, tag2.id)
    assert target.id == tag2.id

    # Check doc now has tag2
    dt = db_session.query(DocumentTag).filter(DocumentTag.document_id == doc.id).first()
    assert dt is not None
    assert dt.tag_id == tag2.id

    # Check tag1 has merged_into_id set
    reloaded_t1 = db_session.query(Tag).filter(Tag.id == tag1.id).first()
    assert reloaded_t1.merged_into_id == tag2.id


def test_tag_delete_reverts_classification(db_session: Session):
    tag = tag_service.create_tag(db_session, "user1", "Lösch-Tag", kind="document_type")
    doc = Document(
        id="doc-del-tag-1",
        owner="user1",
        original_name="test.pdf",
        storage_key="test.pdf",
        mime_type="application/pdf",
        file_size=100,
        sha256="sha-del-1",
        classification_state="classified",
    )
    db_session.add(doc)
    db_session.add(DocumentTag(document_id=doc.id, tag_id=tag.id, source="manual"))
    db_session.commit()

    # Delete tag
    tag_service.delete_tag(db_session, "user1", tag.id)

    db_session.refresh(doc)
    assert doc.classification_state == "needs_review"
