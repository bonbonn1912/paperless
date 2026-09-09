from __future__ import annotations

import io
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, List, Optional
from PIL import Image
import pymupdf as fitz
from sqlalchemy.orm import Session

from app.config import settings
from app.models.base import utc_now
from app.models.capture import CapturePage, CaptureSession
from app.models.document import Document, DocumentAsset
from app.models.job import Job, JobEvent
from app.services.storage import StorageError, storage_service


class CaptureService:
    def create_session(self, db: Session, owner: str) -> CaptureSession:
        now = utc_now()
        expires = now + timedelta(days=settings.CAPTURE_DRAFT_TTL_DAYS)
        session = CaptureSession(
            owner=owner,
            status="draft",
            revision=1,
            expires_at=expires,
        )
        db.add(session)
        db.commit()
        return session

    def add_page_file(
        self,
        db: Session,
        owner: str,
        session_id: str,
        file_stream: BinaryIO,
        filename: str,
        page_number: Optional[int] = None,
    ) -> CapturePage:
        session = db.query(CaptureSession).filter(
            CaptureSession.id == session_id,
            CaptureSession.owner == owner,
            CaptureSession.status == "draft",
        ).first()
        if not session:
            raise ValueError("Draft capture session not found or already finalized.")

        # Determine page number
        if page_number is None:
            max_p = db.query(CapturePage).filter(CapturePage.session_id == session_id).count()
            page_number = max_p + 1

        # Check limits
        if page_number > settings.MAX_CAPTURE_PAGES:
            raise ValueError(f"Exceeded maximum capture pages of {settings.MAX_CAPTURE_PAGES}")

        # Save asset in flat storage
        asset_id = str(uuid.uuid4())
        ext = Path(filename).suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".heic"):
            ext = ".jpg"
        storage_key = f"asset_{asset_id}{ext}"
        target_path = storage_service.get_document_path(storage_key)

        # Write and calculate SHA256
        import hashlib
        hasher = hashlib.sha256()
        total_size = 0
        with open(target_path, "wb") as f:
            while chunk := file_stream.read(64 * 1024):
                total_size += len(chunk)
                hasher.update(chunk)
                f.write(chunk)

        # Create Asset
        asset = DocumentAsset(
            id=asset_id,
            document_id=None,
            capture_session_id=session_id,
            owner=owner,
            storage_key=storage_key,
            role="source_image",
            sha256=hasher.hexdigest(),
            mime_type=f"image/{ext.replace('.', '')}",
            byte_size=total_size,
        )
        db.add(asset)
        db.flush()

        # Create Page
        page = CapturePage(
            session_id=session_id,
            asset_id=asset.id,
            page_number=page_number,
            rotation=0,
            upload_status="uploaded",
        )
        db.add(page)

        session.revision += 1
        db.commit()
        return page

    def patch_session(
        self,
        db: Session,
        owner: str,
        session_id: str,
        pages_patch: list[dict],
        client_revision: int,
    ) -> CaptureSession:
        session = db.query(CaptureSession).filter(
            CaptureSession.id == session_id,
            CaptureSession.owner == owner,
            CaptureSession.status == "draft",
        ).first()
        if not session:
            raise ValueError("Draft session not found.")

        if session.revision != client_revision:
            raise ValueError("Revision conflict. Please reload draft state.")

        for p_data in pages_patch:
            page_id = p_data.get("page_id")
            page = db.query(CapturePage).filter(CapturePage.id == page_id, CapturePage.session_id == session_id).first()
            if page:
                if "page_number" in p_data:
                    page.page_number = p_data["page_number"]
                if "rotation" in p_data:
                    page.rotation = p_data["rotation"] % 360
                if "crop_box" in p_data:
                    page.crop_box = p_data["crop_box"]

        session.revision += 1
        db.commit()
        return session

    def finalize_session(
        self,
        db: Session,
        owner: str,
        session_id: str,
        ordered_page_ids: List[str],
        draft_revision: int,
        title: Optional[str] = None,
    ) -> Document:
        """Freeze capture session and create a new Document queued for assembly & OCR."""
        session = db.query(CaptureSession).filter(
            CaptureSession.id == session_id,
            CaptureSession.owner == owner,
            CaptureSession.status == "draft",
        ).first()
        if not session:
            raise ValueError("Draft session not found or already finalized.")

        # Ensure all pages are uploaded
        pages = db.query(CapturePage).filter(CapturePage.session_id == session_id).all()
        if not pages:
            raise ValueError("Cannot finalize empty capture session.")

        page_map = {p.id: p for p in pages}
        # Validate ordered page IDs
        if len(ordered_page_ids) != len(pages) or set(ordered_page_ids) != set(page_map.keys()):
            raise ValueError("Ordered page IDs do not match all pages in session.")

        # Re-number pages according to ordered list via temporary offset to avoid unique constraint collision
        for idx, pid in enumerate(ordered_page_ids, start=1):
            page_map[pid].page_number = 10000 + idx
        db.flush()

        for idx, pid in enumerate(ordered_page_ids, start=1):
            page_map[pid].page_number = idx
        db.flush()

        session.status = "finalized"

        # Create Document record
        doc_id = str(uuid.uuid4())
        doc_title = title or f"Kamera-Scan {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        doc = Document(
            id=doc_id,
            owner=owner,
            original_name=f"{doc_title}.pdf",
            storage_key=f"pending_assembly_{doc_id}.pdf",  # placeholder until worker assembles PDF
            mime_type="application/pdf",
            file_size=0,
            sha256=f"pending_{doc_id}",
            title=doc_title,
            source="capture",
            processing_state="queued",
            classification_state="pending",
            index_state="pending",
        )
        db.add(doc)
        db.flush()

        # Link source assets to Document
        for p in pages:
            asset = db.query(DocumentAsset).filter(DocumentAsset.id == p.asset_id).first()
            if asset:
                asset.document_id = doc.id

        # Enqueue job
        run_id = str(uuid.uuid4())
        job = Job(
            owner=owner,
            document_id=doc.id,
            run_id=run_id,
            job_type="base_pipeline",
            state="queued",
            step="assembling_document",
            priority=10,
        )
        db.add(job)
        db.flush()

        db.add(JobEvent(
            job_id=job.id,
            from_state="none",
            to_state="queued",
            step="assembling_document",
            reason="Capture session finalized",
        ))

        doc.active_run_id = run_id
        db.commit()
        return doc

    def assemble_pdf_for_document(self, db: Session, document_id: str) -> None:
        """Worker step: Assemble multi-page PDF from rotated/cropped source images."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError("Document not found.")

        # Get pages ordered
        session = (
            db.query(CaptureSession)
            .join(CapturePage, CapturePage.session_id == CaptureSession.id)
            .join(DocumentAsset, DocumentAsset.id == CapturePage.asset_id)
            .filter(DocumentAsset.document_id == document_id)
            .first()
        )
        if not session:
            return

        pages = (
            db.query(CapturePage)
            .filter(CapturePage.session_id == session.id)
            .order_by(CapturePage.page_number)
            .all()
        )

        pdf_doc = fitz.open()  # new empty PDF
        try:
            for p in pages:
                asset = db.query(DocumentAsset).filter(DocumentAsset.id == p.asset_id).first()
                if not asset:
                    continue

                source_img_path = storage_service.get_document_path(asset.storage_key)
                if not source_img_path.exists():
                    continue

                # Load with PIL to apply rotation / crop
                with Image.open(source_img_path) as img:
                    if p.rotation != 0:
                        # PIL rotate is counter-clockwise, negate for clockwise
                        img = img.rotate(-p.rotation, expand=True)

                    if p.crop_box:
                        # e.g. {"x": 10, "y": 10, "w": 100, "h": 100}
                        cb = p.crop_box
                        x0 = cb.get("x", 0)
                        y0 = cb.get("y", 0)
                        x1 = x0 + cb.get("w", img.width)
                        y1 = y0 + cb.get("h", img.height)
                        img = img.crop((x0, y0, min(x1, img.width), min(y1, img.height)))

                    # Convert to RGB bytes
                    img_byte_arr = io.BytesIO()
                    img.convert("RGB").save(img_byte_arr, format="JPEG", quality=90)
                    img_bytes = img_byte_arr.getvalue()

                # Insert page into PDF
                img_doc = fitz.open("jpeg", img_bytes)
                rect = img_doc[0].rect
                pdf_page = pdf_doc.new_page(width=rect.width, height=rect.height)
                pdf_page.insert_image(rect, stream=img_bytes)
                img_doc.close()

            final_storage_key = f"{doc.id}.pdf"
            final_path = storage_service.get_document_path(final_storage_key)
            pdf_doc.save(str(final_path), garbage=4, deflate=True)
            pdf_doc.close()

            # Calculate SHA256 and size
            import hashlib
            with open(final_path, "rb") as f:
                data = f.read()
                pdf_sha256 = hashlib.sha256(data).hexdigest()
                pdf_size = len(data)

            doc.storage_key = final_storage_key
            doc.sha256 = pdf_sha256
            doc.file_size = pdf_size

            # Create asset for assembled PDF
            assembled_asset = DocumentAsset(
                id=str(uuid.uuid4()),
                document_id=doc.id,
                owner=doc.owner,
                storage_key=final_storage_key,
                role="assembled_pdf",
                sha256=pdf_sha256,
                mime_type="application/pdf",
                byte_size=pdf_size,
            )
            db.add(assembled_asset)
            db.commit()

        except Exception:
            pdf_doc.close()
            raise


capture_service = CaptureService()
