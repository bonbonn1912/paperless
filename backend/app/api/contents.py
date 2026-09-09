from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.document import Document, DocumentPage
from app.schemas.document import DocumentViewerManifest
from app.services.search import search_service
from app.services.storage import storage_service

router = APIRouter(prefix="/documents", tags=["contents"])


def _range_streamer(file_path: Path, start: int, end: int, chunk_size: int = 64 * 1024) -> Generator[bytes, None, None]:
    with open(file_path, "rb") as f:
        f.seek(start)
        bytes_left = end - start + 1
        while bytes_left > 0:
            read_len = min(chunk_size, bytes_left)
            data = f.read(read_len)
            if not data:
                break
            bytes_left -= len(data)
            yield data


def parse_byte_range(range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
    """Parse HTTP Range header supporting:
       - bytes=start-end (e.g. bytes=0-1024)
       - bytes=start-    (e.g. bytes=1024-)
       - bytes=-suffix   (e.g. bytes=-2048, used by PDF.js for trailer/xref)
    """
    if not range_header or not range_header.startswith("bytes="):
        return None
    range_val = range_header[6:].strip()
    if "," in range_val:
        range_val = range_val.split(",")[0].strip()

    # Suffix range: bytes=-2048
    suffix_match = re.match(r"^-(?P<suffix>\d+)$", range_val)
    if suffix_match:
        suffix_len = int(suffix_match.group("suffix"))
        if suffix_len <= 0 or file_size == 0:
            return None
        start = max(0, file_size - suffix_len)
        end = file_size - 1
        return start, end

    # Standard range: bytes=start-end or bytes=start-
    range_match = re.match(r"^(?P<start>\d+)-(?P<end>\d*)$", range_val)
    if range_match:
        start = int(range_match.group("start"))
        end_str = range_match.group("end")
        end = int(end_str) if end_str else file_size - 1
        if start >= file_size or start > end:
            return None
        end = min(end, file_size - 1)
        return start, end

    return None


@router.get("/{document_id}/file")
def get_document_file(
    document_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
    range_header: Optional[str] = Header(None, alias="range"),
) -> Response:
    """Serve document file supporting HTTP Range requests for PDF.js streaming."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner == user, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    file_path = storage_service.get_document_path(doc.storage_key)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file missing on disk")

    file_size = os.path.getsize(file_path)

    # Check Range header
    if range_header:
        byte_range = parse_byte_range(range_header, file_size)
        if not byte_range:
            return Response(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                headers={
                    "Content-Range": f"bytes */{file_size}",
                    "Accept-Ranges": "bytes",
                },
            )

        start, end = byte_range
        content_length = end - start + 1
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": doc.mime_type,
            "Content-Disposition": f'inline; filename="{doc.original_name}"',
            "Cache-Control": "no-store",
            "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length",
        }
        return StreamingResponse(
            _range_streamer(file_path, start, end),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            headers=headers,
        )

    # Full response
    return FileResponse(
        path=str(file_path),
        media_type=doc.mime_type,
        filename=doc.original_name,
        content_disposition_type="inline",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-store",
            "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length",
        },
    )


@router.get("/{document_id}/thumbnail")
def get_document_thumbnail(
    document_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner == user, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    thumb_path = storage_service.generate_thumbnail(doc.id, doc.storage_key, doc.mime_type)
    if not thumb_path or not thumb_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not available")

    return FileResponse(
        path=str(thumb_path),
        media_type="image/webp",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.get("/{document_id}/pages/{page_number}/file")
def get_document_page_file(
    document_id: str,
    page_number: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve rendered page image for viewer thumbnails."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner == user, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    page_path = storage_service.get_page_image(doc.id, doc.storage_key, doc.mime_type, page_number)
    if not page_path or not page_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page image not available")

    return FileResponse(
        path=str(page_path),
        media_type="image/webp",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.get("/{document_id}/viewer-manifest")
@router.get("/{document_id}/viewer")
def get_document_viewer_manifest(
    document_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> DocumentViewerManifest:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner == user, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    pages = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
        .all()
    )

    page_manifests = [
        {
            "page_number": p.page_number,
            "width": p.width or 595.0,
            "height": p.height or 842.0,
            "has_text": bool(p.extracted_text),
            "state": p.page_state,
        }
        for p in pages
    ]

    return DocumentViewerManifest(
        document_id=doc.id,
        mime_type=doc.mime_type,
        file_size=doc.file_size,
        total_pages=len(page_manifests),
        pages=page_manifests,
        file_url=f"/api/v1/documents/{doc.id}/file",
        thumbnail_url=f"/api/v1/documents/{doc.id}/thumbnail",
        can_search=True,
    )


@router.get("/{document_id}/search")
def search_inside_document(
    document_id: str,
    user: CurrentUser,
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    hits = search_service.search_in_document(db, user, document_id, q)
    return {
        "document_id": document_id,
        "query": q,
        "total_hits": len(hits),
        "hits": hits,
    }
