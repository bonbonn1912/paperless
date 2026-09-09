from __future__ import annotations

import io
from PIL import Image
from sqlalchemy.orm import Session

from app.models.capture import CapturePage, CaptureSession
from app.models.document import Document, DocumentAsset
from app.services.capture import capture_service


def test_capture_session_and_pdf_assembly(db_session: Session, sample_image_bytes: bytes):
    owner = "user_camera"

    # 1. Create session
    session = capture_service.create_session(db_session, owner)
    assert session.status == "draft"

    # 2. Add two pages
    stream1 = io.BytesIO(sample_image_bytes)
    stream2 = io.BytesIO(sample_image_bytes)
    p1 = capture_service.add_page_file(db_session, owner, session.id, stream1, "page1.jpg", page_number=1)
    p2 = capture_service.add_page_file(db_session, owner, session.id, stream2, "page2.jpg", page_number=2)

    assert p1.page_number == 1
    assert p2.page_number == 2

    # 3. Patch: rotate page 1 by 90 deg and reorder
    capture_service.patch_session(
        db=db_session,
        owner=owner,
        session_id=session.id,
        pages_patch=[{"page_id": p1.id, "rotation": 90}],
        client_revision=session.revision,
    )
    db_session.refresh(p1)
    assert p1.rotation == 90

    # 4. Finalize
    doc = capture_service.finalize_session(
        db=db_session,
        owner=owner,
        session_id=session.id,
        ordered_page_ids=[p2.id, p1.id],  # reverse order
        draft_revision=session.revision,
        title="Mein Kamera-Scan",
    )
    assert doc.id is not None
    assert doc.source == "capture"
    assert doc.processing_state == "queued"

    # 5. Assemble PDF
    capture_service.assemble_pdf_for_document(db_session, doc.id)
    db_session.refresh(doc)
    assert doc.storage_key.endswith(".pdf")
    assert doc.file_size > 0
    assert not doc.sha256.startswith("pending_")

    # Verify source image assets are preserved
    assets = db_session.query(DocumentAsset).filter(DocumentAsset.document_id == doc.id).all()
    roles = {a.role for a in assets}
    assert "source_image" in roles
    assert "assembled_pdf" in roles
