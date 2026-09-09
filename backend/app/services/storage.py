from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Optional, Tuple
from PIL import Image
import pymupdf as fitz
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document import Document

SUPPORTED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heic",
}


class StorageError(Exception):
    pass


class DuplicateDocumentError(Exception):
    def __init__(self, existing_document_id: str):
        super().__init__(f"Document already exists: {existing_document_id}")
        self.existing_document_id = existing_document_id


def detect_mime_type(sample_bytes: bytes, filename: str) -> Optional[str]:
    """Detect MIME type from file header bytes and extension."""
    if sample_bytes.startswith(b"%PDF"):
        return "application/pdf"
    if sample_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if sample_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if sample_bytes[:4] == b"RIFF" and sample_bytes[8:12] == b"WEBP":
        return "image/webp"
    # HEIF/HEIC checks ftyp box
    if len(sample_bytes) >= 12 and sample_bytes[4:8] == b"ftyp":
        major_brand = sample_bytes[8:12].lower()
        if major_brand in (b"heic", b"heix", b"hevc", b"mif1", b"msf1"):
            return "image/heic"

    # Extension-based fallback check
    ext = Path(filename).suffix.lower()
    for mime, m_ext in SUPPORTED_MIME_TYPES.items():
        if ext == m_ext:
            return mime
    return None


class StorageService:
    def __init__(self) -> None:
        settings.ensure_directories()

    def get_document_path(self, storage_key: str) -> Path:
        return settings.documents_dir / storage_key

    def get_derived_dir(self, document_id: str) -> Path:
        p = settings.derived_dir / document_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _finalize_staging_file(
        self,
        db: Session,
        staging_file: Path,
        owner: str,
        original_filename: str,
        total_size: int,
        sha256_hash: str,
        sample_bytes: bytes,
    ) -> Tuple[str, str, int, str, str]:
        if total_size == 0:
            raise StorageError("Uploaded file is empty.")

        # Check for duplicate document for the same owner
        existing = (
            db.query(Document)
            .filter(
                Document.owner == owner,
                Document.sha256 == sha256_hash,
                Document.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            raise DuplicateDocumentError(existing.id)

        mime_type = detect_mime_type(sample_bytes, original_filename)
        if not mime_type or mime_type not in SUPPORTED_MIME_TYPES:
            raise StorageError(f"Unsupported file format for '{original_filename}'. Supported: PDF, JPG, PNG, WEBP, HEIC")

        # Validate file content integrity
        self._validate_file_integrity(staging_file, mime_type)

        # Atomic move to documents
        ext = SUPPORTED_MIME_TYPES[mime_type]
        doc_uuid = str(uuid.uuid4())
        storage_key = f"{doc_uuid}{ext}"
        final_path = self.get_document_path(storage_key)

        shutil.move(str(staging_file), str(final_path))
        return doc_uuid, storage_key, total_size, sha256_hash, mime_type

    def save_upload_stream(
        self,
        db: Session,
        owner: str,
        stream: BinaryIO,
        original_filename: str,
        content_length: Optional[int] = None,
    ) -> Tuple[str, str, int, str, str]:
        if content_length and content_length > settings.MAX_UPLOAD_MB * 1024 * 1024:
            raise StorageError(f"File size exceeds maximum upload limit of {settings.MAX_UPLOAD_MB} MB")

        staging_id = str(uuid.uuid4())
        staging_file = settings.staging_dir / f"staging_{staging_id}.tmp"

        hasher = hashlib.sha256()
        total_size = 0
        sample_bytes = b""

        try:
            with open(staging_file, "wb") as f:
                while chunk := stream.read(64 * 1024):
                    total_size += len(chunk)
                    if total_size > settings.MAX_UPLOAD_MB * 1024 * 1024:
                        raise StorageError(f"File exceeds maximum upload limit of {settings.MAX_UPLOAD_MB} MB")
                    hasher.update(chunk)
                    if len(sample_bytes) < 4096:
                        sample_bytes += chunk[: 4096 - len(sample_bytes)]
                    f.write(chunk)

            return self._finalize_staging_file(
                db, staging_file, owner, original_filename, total_size, hasher.hexdigest(), sample_bytes
            )
        except Exception:
            if staging_file.exists():
                staging_file.unlink(missing_ok=True)
            raise

    async def save_async_stream(
        self,
        db: Session,
        owner: str,
        stream_gen,
        original_filename: str,
        content_length: Optional[int] = None,
    ) -> Tuple[str, str, int, str, str]:
        if content_length and content_length > settings.MAX_UPLOAD_MB * 1024 * 1024:
            raise StorageError(f"File size exceeds maximum upload limit of {settings.MAX_UPLOAD_MB} MB")

        staging_id = str(uuid.uuid4())
        staging_file = settings.staging_dir / f"staging_{staging_id}.tmp"

        hasher = hashlib.sha256()
        total_size = 0
        sample_bytes = b""

        try:
            with open(staging_file, "wb") as f:
                async for chunk in stream_gen:
                    if not chunk:
                        continue
                    total_size += len(chunk)
                    if total_size > settings.MAX_UPLOAD_MB * 1024 * 1024:
                        raise StorageError(f"File exceeds maximum upload limit of {settings.MAX_UPLOAD_MB} MB")
                    hasher.update(chunk)
                    if len(sample_bytes) < 4096:
                        sample_bytes += chunk[: 4096 - len(sample_bytes)]
                    f.write(chunk)

            return self._finalize_staging_file(
                db, staging_file, owner, original_filename, total_size, hasher.hexdigest(), sample_bytes
            )
        except Exception:
            if staging_file.exists():
                staging_file.unlink(missing_ok=True)
            raise


    def _validate_file_integrity(self, file_path: Path, mime_type: str) -> None:
        """Ensure file is not corrupt or password-protected."""
        if mime_type == "application/pdf":
            try:
                doc = fitz.open(str(file_path))
                if doc.is_encrypted:
                    raise StorageError("Password-protected PDFs are not supported.")
                if doc.page_count == 0:
                    raise StorageError("PDF has no pages.")
                if doc.page_count > settings.MAX_PDF_PAGES:
                    raise StorageError(f"PDF exceeds maximum page limit of {settings.MAX_PDF_PAGES} pages.")
                doc.close()
            except fitz.FileDataError as e:
                raise StorageError(f"Corrupt PDF file: {e}")
        elif mime_type.startswith("image/"):
            try:
                with Image.open(file_path) as img:
                    img.verify()
                    w, h = img.size
                    if w * h > settings.MAX_IMAGE_PIXELS:
                        raise StorageError(f"Image dimensions exceed maximum pixel limit of {settings.MAX_IMAGE_PIXELS} pixels.")
            except Exception as e:
                raise StorageError(f"Corrupt or invalid image file: {e}")

    def generate_thumbnail(self, document_id: str, storage_key: str, mime_type: str) -> Optional[Path]:
        """Generate a thumbnail image for the document in derived/."""
        source_path = self.get_document_path(storage_key)
        if not source_path.exists():
            return None

        derived_dir = self.get_derived_dir(document_id)
        thumb_path = derived_dir / "thumbnail.webp"
        if thumb_path.exists():
            return thumb_path

        try:
            if mime_type == "application/pdf":
                doc = fitz.open(str(source_path))
                if doc.page_count > 0:
                    page = doc.load_page(0)
                    pix = page.get_pixmap(dpi=100)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img.thumbnail((400, 400))
                    img.save(str(thumb_path), format="WEBP", quality=80)
                doc.close()
            elif mime_type.startswith("image/"):
                with Image.open(source_path) as img:
                    img = img.convert("RGB")
                    img.thumbnail((400, 400))
                    img.save(str(thumb_path), format="WEBP", quality=80)

            return thumb_path if thumb_path.exists() else None
        except Exception:
            return None


storage_service = StorageService()
