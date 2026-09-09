from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentFieldOverride
from app.models.tag import DocumentTag, DocumentTagOverride
from app.services.classifier import classifier
from app.services.tags import tag_service


def test_manual_review_and_protection_from_reprocessing(db_session: Session):
    owner = "user_review"
    tag_service.ensure_default_tags(db_session, owner)
    tag_rechnungen, _, _ = tag_service.resolve_name(db_session, owner, "Rechnungen")
    tag_vertraege, _, _ = tag_service.resolve_name(db_session, owner, "Verträge")

    doc = Document(
        id="doc-rev-1",
        owner=owner,
        original_name="unbekannt.pdf",
        storage_key="unbekannt.pdf",
        mime_type="application/pdf",
        file_size=500,
        sha256="sha-rev-1",
        classification_state="needs_review",
    )
    db_session.add(doc)
    db_session.commit()

    # User manually confirms tag_vertraege and excludes tag_rechnungen
    db_session.add(DocumentTag(document_id=doc.id, tag_id=tag_vertraege.id, source="manual"))
    db_session.add(DocumentTagOverride(document_id=doc.id, tag_id=tag_vertraege.id, state="confirmed", owner=owner))
    db_session.add(DocumentTagOverride(document_id=doc.id, tag_id=tag_rechnungen.id, state="excluded", owner=owner))

    # User manually sets title override
    db_session.add(DocumentFieldOverride(document_id=doc.id, field_name="title", value="Mein Manueller Vertrag", owner=owner))
    doc.classification_state = "classified"
    db_session.commit()

    # Now simulate classifier running again (reprocessing) with text that would normally trigger "Rechnungen"
    fake_invoice_text = "Rechnungsnummer: 12345 Gesamtbetrag: 100 EUR Zahlbar sofort."
    fake_metadata = {"amount": 10000, "title": "Automatische Rechnung"}

    state, reasons, candidates = classifier.classify_document(
        db=db_session,
        owner=owner,
        document_id=doc.id,
        full_text=fake_invoice_text,
        metadata=fake_metadata,
        run_id="run-test",
    )

    # Document remains classified and respects confirmed tags!
    assert state == "classified"
    # Tag Rechnungen must NOT be added because it was excluded by user
    assigned_tags = db_session.query(DocumentTag).filter(DocumentTag.document_id == doc.id).all()
    assigned_ids = {at.tag_id for at in assigned_tags}
    assert tag_vertraege.id in assigned_ids
    assert tag_rechnungen.id not in assigned_ids
