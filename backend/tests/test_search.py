from __future__ import annotations

from datetime import date
import pytest
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentPage
from app.services.folders import folder_service
from app.services.search import search_service
from app.services.tags import tag_service


def test_fts5_and_faceted_search(db_session: Session):
    owner = "user_search"
    tag_service.ensure_default_tags(db_session, owner)

    # Create 2 documents
    doc1 = Document(
        id="doc-s-1",
        owner=owner,
        original_name="stromrechnung_2026.pdf",
        storage_key="s1.pdf",
        mime_type="application/pdf",
        file_size=1000,
        sha256="hash1",
        title="Stadtwerke Stromrechnung",
        sender="Stadtwerke München",
        document_date=date(2026, 3, 1),
        classification_state="classified",
    )
    doc2 = Document(
        id="doc-s-2",
        owner=owner,
        original_name="mietvertrag.pdf",
        storage_key="s2.pdf",
        mime_type="application/pdf",
        file_size=2000,
        sha256="hash2",
        title="Wohnungsmietvertrag",
        sender="Hausverwaltung Schmidt",
        document_date=date(2026, 1, 15),
        classification_state="classified",
    )
    db_session.add_all([doc1, doc2])
    db_session.flush()

    # Add pages
    p1 = DocumentPage(
        document_id=doc1.id,
        page_number=1,
        extracted_text="Jahresabrechnung Strom und Gas für Zählernummer 987654. Gesamtbetrag 450 Euro.",
        word_boxes=[{"text": "Strom", "x0": 50, "y0": 100, "x1": 90, "y1": 115}],
    )
    p2 = DocumentPage(
        document_id=doc2.id,
        page_number=1,
        extracted_text="Mietvertrag über die Wohnräume in Berlin. Kaltmiete monatlich 800 Euro.",
    )
    db_session.add_all([p1, p2])
    db_session.commit()

    # Index both
    search_service.update_document_index(db_session, doc1.id, owner)
    search_service.update_document_index(db_session, doc2.id, owner)

    # 1. Search for "Strom"
    docs, count, snippets = search_service.search_documents(db_session, owner, query="Strom")
    assert count == 1
    assert docs[0].id == doc1.id
    assert doc1.id in snippets

    # 2. Prefix search: "Zähler*"
    docs_prefix, count_prefix, _ = search_service.search_documents(db_session, owner, query="Zähler")
    assert count_prefix == 1
    assert docs_prefix[0].id == doc1.id

    # 3. In-document search
    hits = search_service.search_in_document(db_session, owner, doc1.id, "Strom")
    assert len(hits) == 1
    assert hits[0]["page_number"] == 1
    assert len(hits[0]["boxes"]) >= 1
    assert hits[0]["boxes"][0]["x0"] == 50
