from __future__ import annotations

import io
import uuid
import pytest
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.job import Job
from app.models.tag import DocumentTag, Tag
from app.processing.pipeline import pipeline
from app.services.search import search_service
from app.services.storage import storage_service
from app.services.tags import tag_service


def test_complete_base_pipeline_e2e(db_session: Session, sample_pdf_bytes: bytes):
    owner = "pipeline_tester"
    tag_service.ensure_default_tags(db_session, owner)

    # 1. Save uploaded file
    stream = io.BytesIO(sample_pdf_bytes)
    doc_uuid, storage_key, file_size, sha256_hash, mime_type = storage_service.save_upload_stream(
        db=db_session,
        owner=owner,
        stream=stream,
        original_filename="rechnung_musterfirma.pdf",
    )

    doc = Document(
        id=doc_uuid,
        owner=owner,
        original_name="rechnung_musterfirma.pdf",
        storage_key=storage_key,
        mime_type=mime_type,
        file_size=file_size,
        sha256=sha256_hash,
        title="rechnung_musterfirma.pdf",
        source="upload",
        processing_state="queued",
        classification_state="pending",
        index_state="pending",
    )
    db_session.add(doc)
    db_session.flush()

    run_id = str(uuid.uuid4())
    job = Job(
        owner=owner,
        document_id=doc.id,
        run_id=run_id,
        job_type="base_pipeline",
        state="queued",
        step="queued",
        priority=10,
    )
    db_session.add(job)
    db_session.commit()

    # 2. Run pipeline
    pipeline.execute_base_pipeline(db_session, job, "dummy-token")

    # 3. Assertions
    db_session.refresh(doc)
    assert doc.processing_state == "ready"
    assert doc.index_state == "ready"
    assert doc.classification_state == "classified"
    assert doc.amount == 14999
    assert doc.currency == "EUR"
    assert doc.document_date is not None
    assert doc.document_date.isoformat() == "2026-03-15"

    # Verify canonical tag Rechnungen assigned
    assigned = (
        db_session.query(Tag.name)
        .join(DocumentTag, DocumentTag.tag_id == Tag.id)
        .filter(DocumentTag.document_id == doc.id)
        .all()
    )
    tag_names = [a[0] for a in assigned]
    assert "Rechnungen" in tag_names

    # Verify FTS5 search finds the document
    docs, count, _ = search_service.search_documents(db_session, owner, query="Beratungsleistung")
    assert count == 1
    assert docs[0].id == doc.id

    docs2, count2, _ = search_service.search_documents(db_session, owner, query="RE-2026-0042")
    assert count2 == 1
    assert docs2[0].id == doc.id
