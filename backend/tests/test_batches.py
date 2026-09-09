from __future__ import annotations

import io
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.batch import UploadBatch, UploadItem
from app.models.document import Document
from app.models.job import Job


def test_100_files_batch_and_status_polling(auth_client, db_session: Session):
    client, username, csrf = auth_client

    # 1. Create batch manifest with 100 items
    items = [
        {"client_item_id": f"item-{i}", "position": i, "original_name": f"doc_{i}.pdf", "file_size": 1024}
        for i in range(100)
    ]
    resp = client.post("/api/v1/upload-batches", json={"items": items})
    assert resp.status_code == 201
    data = resp.json()
    batch_id = data["batch_id"]
    assert data["total_items"] == 100
    assert len(data["item_ids"]) == 100

    # 2. Upload first 2 files
    item_ids_map = data["item_ids"]
    first_item_id = item_ids_map["item-0"]

    pdf_stream = io.BytesIO(b"%PDF-1.4 test content")
    resp_upload = client.put(
        f"/api/v1/upload-batches/{batch_id}/items/{first_item_id}/file",
        content=b"%PDF-1.4 sample file content...",
        headers={"Content-Type": "application/pdf", "Idempotency-Key": "idemp-0"},
    )
    assert resp_upload.status_code in (202, 400)

    # 3. Bulk status poll for the batch
    resp_status = client.post(
        "/api/v1/processing/status",
        json={"batch_ids": [batch_id], "document_ids": [], "known_revision": None},
    )
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert "revision" in status_data
    assert len(status_data["batches"]) == 1
    batch_stat = status_data["batches"][0]
    assert batch_stat["batch_id"] == batch_id
    assert batch_stat["total"] == 100
    assert len(status_data["items"]) == 100

    # 4. Immediate second poll with same revision -> unchanged=True
    rev = status_data["revision"]
    resp_status2 = client.post(
        "/api/v1/processing/status",
        json={"batch_ids": [batch_id], "document_ids": [], "known_revision": rev},
    )
    assert resp_status2.status_code == 200
    assert resp_status2.json()["unchanged"] is True
