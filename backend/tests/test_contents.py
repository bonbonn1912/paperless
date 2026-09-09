from __future__ import annotations

import io
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentPage
from app.services.storage import storage_service


def test_contents_viewer_manifest_and_file_streaming(
    auth_client: tuple[TestClient, str, str],
    db_session: Session,
    sample_pdf_bytes: bytes,
):
    client, owner, _ = auth_client

    # 1. Save uploaded PDF
    stream = io.BytesIO(sample_pdf_bytes)
    doc_uuid, storage_key, file_size, sha256_hash, mime_type = storage_service.save_upload_stream(
        db=db_session,
        owner=owner,
        stream=stream,
        original_filename="sample.pdf",
    )

    doc = Document(
        id=doc_uuid,
        owner=owner,
        original_name="sample.pdf",
        storage_key=storage_key,
        mime_type=mime_type,
        file_size=file_size,
        sha256=sha256_hash,
        title="Sample Document",
        processing_state="ready",
        classification_state="classified",
    )
    page1 = DocumentPage(document_id=doc_uuid, page_number=1, width=595, height=842, extracted_text="Page 1 text")
    page2 = DocumentPage(document_id=doc_uuid, page_number=2, width=595, height=842, extracted_text="Page 2 text")
    db_session.add_all([doc, page1, page2])
    db_session.commit()

    # 2. Test viewer-manifest endpoint (both routes)
    resp1 = client.get(f"/api/v1/documents/{doc_uuid}/viewer-manifest")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["total_pages"] == 2
    assert len(data1["pages"]) == 2

    resp2 = client.get(f"/api/v1/documents/{doc_uuid}/viewer")
    assert resp2.status_code == 200
    assert resp2.json()["total_pages"] == 2

    # 3. Test full file download (inline content disposition)
    resp_full = client.get(f"/api/v1/documents/{doc_uuid}/file")
    assert resp_full.status_code == 200
    assert resp_full.headers["content-type"] == "application/pdf"
    assert "inline" in resp_full.headers.get("content-disposition", "")
    assert resp_full.headers.get("accept-ranges") == "bytes"
    assert len(resp_full.content) == file_size

    # 4. Test Range request: prefix (bytes=0-99)
    resp_range_prefix = client.get(f"/api/v1/documents/{doc_uuid}/file", headers={"Range": "bytes=0-99"})
    assert resp_range_prefix.status_code == 206
    assert resp_range_prefix.headers["content-range"] == f"bytes 0-99/{file_size}"
    assert len(resp_range_prefix.content) == 100

    # 5. Test Range request: suffix (bytes=-500) as used by PDF.js for xref trailer
    resp_range_suffix = client.get(f"/api/v1/documents/{doc_uuid}/file", headers={"Range": "bytes=-500"})
    assert resp_range_suffix.status_code == 206
    start_expected = max(0, file_size - 500)
    assert resp_range_suffix.headers["content-range"] == f"bytes {start_expected}-{file_size - 1}/{file_size}"
    assert len(resp_range_suffix.content) == min(500, file_size)

    # 6. Test thumbnail endpoint
    resp_thumb = client.get(f"/api/v1/documents/{doc_uuid}/thumbnail")
    assert resp_thumb.status_code == 200
    assert resp_thumb.headers["content-type"] == "image/webp"

    # 7. Test pages endpoint for page 1 and page 2
    resp_p1 = client.get(f"/api/v1/documents/{doc_uuid}/pages/1/file")
    assert resp_p1.status_code == 200
    assert resp_p1.headers["content-type"] == "image/webp"

    resp_p2 = client.get(f"/api/v1/documents/{doc_uuid}/pages/2/file")
    assert resp_p2.status_code == 200
    assert resp_p2.headers["content-type"] == "image/webp"

    # Page out of range should return 404
    resp_p99 = client.get(f"/api/v1/documents/{doc_uuid}/pages/99/file")
    assert resp_p99.status_code == 404
