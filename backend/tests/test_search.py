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


def test_hidden_keywords_trigger_search_without_visible_tags(db_session: Session):
    import json
    owner = "user_hidden_kw"
    tag_service.ensure_default_tags(db_session, owner)

    # 1. Create a document with max 2 visible tags
    tag1 = tag_service.create_tag(db_session, owner, "Wanderführer", kind="topic")
    tag2 = tag_service.create_tag(db_session, owner, "Alpen", kind="topic")

    doc = Document(
        id="doc-semantic-search-1",
        owner=owner,
        original_name="tourenplan_2026.pdf",
        storage_key="tour.pdf",
        mime_type="application/pdf",
        file_size=1500,
        sha256="hash_tour_123",
        title="Bergwanderung Tirol",
        sender="Alpenverein",
        classification_state="classified",
        # 50 semantic search keywords not present in OCR text
        search_keywords=json.dumps([
            "Geodäsie", "Kartographie", "Höhenmessung", "GPS-Navigation",
            "Topographie", "Wetterumschwung", "Biwak", "Gipfelkreuz"
        ], ensure_ascii=False),
    )
    db_session.add(doc)
    db_session.flush()

    # Add visible tags (max 2)
    from app.models.tag import DocumentTag
    db_session.add(DocumentTag(document_id=doc.id, tag_id=tag1.id, source="ai"))
    db_session.add(DocumentTag(document_id=doc.id, tag_id=tag2.id, source="ai"))

    # Add OCR page that does NOT contain "Geodäsie" or "GPS-Navigation"
    page = DocumentPage(
        document_id=doc.id,
        page_number=1,
        extracted_text="Einfache Route von Innsbruck zur Hütte. Gehzeit etwa 4 Stunden.",
    )
    db_session.add(page)
    db_session.commit()

    # Index the document
    search_service.update_document_index(db_session, doc.id, owner)

    # Search for term only present in search_keywords ("Geodäsie")
    docs, count, snippets = search_service.search_documents(db_session, owner, query="Geodäsie")
    assert count == 1
    assert docs[0].id == doc.id
    assert doc.id in snippets

    # Search for another semantic keyword ("GPS-Navigation")
    docs_gps, count_gps, _ = search_service.search_documents(db_session, owner, query="GPS-Navigation")
    assert count_gps == 1
    assert docs_gps[0].id == doc.id

    # Verify that the visible tags in DB are strictly ONLY the 2 assigned tags
    assigned = db_session.query(DocumentTag).filter(DocumentTag.document_id == doc.id).all()
    assert len(assigned) == 2
    assert len(assigned) <= 3  # Max 3 tags requirement

    # Verify that none of the 50 keywords were created as tags
    from app.models.tag import Tag
    all_owner_tags = [t.name for t in db_session.query(Tag).filter(Tag.owner == owner).all()]
    assert "Geodäsie" not in all_owner_tags
    assert "GPS-Navigation" not in all_owner_tags
    assert "Wanderführer" in all_owner_tags
    assert "Alpen" in all_owner_tags
