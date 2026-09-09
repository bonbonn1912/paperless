from __future__ import annotations

from typing import Callable, Optional
import pymupdf as fitz
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentFieldOverride, DocumentPage
from app.models.job import Job
from app.providers.tesseract import tesseract_provider
from app.services.capture import capture_service
from app.services.classifier import classifier
from app.services.metadata_extractor import metadata_extractor
from app.services.search import search_service
from app.services.storage import storage_service
from app.services.tags import tag_service


class PipelineExecutionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class DocumentPipeline:
    def execute_base_pipeline(
        self,
        db: Session,
        job: Job,
        claim_token: str,
        heartbeat_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Execute all steps of the base document pipeline with page checkpointing."""
        if not job.document_id:
            raise PipelineExecutionError("no_document", "Job has no associated document")

        doc = db.query(Document).filter(Document.id == job.document_id).first()
        if not doc or doc.deleted_at is not None:
            raise PipelineExecutionError("cancelled", "Document deleted or does not exist")

        owner = doc.owner
        tag_service.ensure_default_tags(db, owner)

        # Step 1: Document assembly (if camera series)
        if doc.source == "capture" and doc.storage_key.startswith("pending_assembly_"):
            job.step = "assembling_document"
            db.commit()
            if heartbeat_callback:
                heartbeat_callback()
            capture_service.assemble_pdf_for_document(db, doc.id)
            # Reload doc after assembly
            db.refresh(doc)

        file_path = storage_service.get_document_path(doc.storage_key)
        if not file_path.exists():
            raise PipelineExecutionError("missing_file", f"Original file {doc.storage_key} not found")

        # Step 2: Extraction & OCR (Page by Page Checkpointing)
        job.step = "extracting_text"
        doc.processing_state = "processing"
        db.commit()

        if doc.mime_type == "application/pdf":
            try:
                pdf_doc = fitz.open(str(file_path))
                total_pages = pdf_doc.page_count
            except Exception as e:
                raise PipelineExecutionError("corrupt_file", f"Failed to open PDF: {e}")

            for page_idx in range(total_pages):
                page_num = page_idx + 1

                # Check if page was already extracted (resuming after restart/interruption)
                existing_page = (
                    db.query(DocumentPage)
                    .filter(DocumentPage.document_id == doc.id, DocumentPage.page_number == page_num)
                    .first()
                )

                if not existing_page or existing_page.page_state != "ocr_done":
                    if heartbeat_callback:
                        heartbeat_callback()

                    job.step = "ocr"
                    text_out, method, conf, boxes, w, h = tesseract_provider.extract_page_data(
                        pdf_doc, page_idx, lang="deu+eng", dpi=250
                    )

                    if not existing_page:
                        doc_page = DocumentPage(
                            document_id=doc.id,
                            page_number=page_num,
                            extracted_text=text_out,
                            extraction_method=method,
                            ocr_confidence=conf,
                            page_state="ocr_done",
                            width=w,
                            height=h,
                            word_boxes=boxes,
                        )
                        db.add(doc_page)
                    else:
                        existing_page.extracted_text = text_out
                        existing_page.extraction_method = method
                        existing_page.ocr_confidence = conf
                        existing_page.page_state = "ocr_done"
                        existing_page.width = w
                        existing_page.height = h
                        existing_page.word_boxes = boxes

                    job.progress = {"processed_pages": page_num, "total_pages": total_pages}
                    doc.index_state = "partial"
                    db.commit()

            pdf_doc.close()

        elif doc.mime_type.startswith("image/"):
            # Single image document
            existing_page = (
                db.query(DocumentPage)
                .filter(DocumentPage.document_id == doc.id, DocumentPage.page_number == 1)
                .first()
            )
            if not existing_page:
                job.step = "ocr"
                db.commit()
                if heartbeat_callback:
                    heartbeat_callback()
                text_out, method, conf, boxes, w, h = tesseract_provider.extract_image_data(
                    str(file_path), lang="deu+eng"
                )
                doc_page = DocumentPage(
                    document_id=doc.id,
                    page_number=1,
                    extracted_text=text_out,
                    extraction_method=method,
                    ocr_confidence=conf,
                    page_state="ocr_done",
                    width=w,
                    height=h,
                    word_boxes=boxes,
                )
                db.add(doc_page)
                job.progress = {"processed_pages": 1, "total_pages": 1}
                doc.index_state = "partial"
                db.commit()

        # Step 3: Extract Metadata
        job.step = "extracting_metadata"
        db.commit()
        pages = (
            db.query(DocumentPage)
            .filter(DocumentPage.document_id == doc.id)
            .order_by(DocumentPage.page_number)
            .all()
        )
        full_text = "\n\n".join([p.extracted_text for p in pages if p.extracted_text])

        extracted = metadata_extractor.extract_metadata(full_text, doc.original_name)

        # Check manual field overrides
        overrides = {
            fo.field_name: fo.value
            for fo in db.query(DocumentFieldOverride).filter(DocumentFieldOverride.document_id == doc.id).all()
        }

        if "title" not in overrides and not doc.title and extracted.get("title"):
            doc.title = extracted["title"]
        if "sender" not in overrides and not doc.sender and extracted.get("sender"):
            doc.sender = extracted["sender"]
        if "document_date" not in overrides and not doc.document_date and extracted.get("document_date"):
            doc.document_date = extracted["document_date"]
        if "due_date" not in overrides and not doc.due_date and extracted.get("due_date"):
            doc.due_date = extracted["due_date"]
        if "amount" not in overrides and doc.amount is None and extracted.get("amount") is not None:
            doc.amount = extracted["amount"]
            doc.currency = extracted.get("currency", "EUR")

        # Step 4: Classifying
        job.step = "classifying"
        db.commit()
        if heartbeat_callback:
            heartbeat_callback()

        class_state, review_reasons, _ = classifier.classify_document(
            db=db,
            owner=owner,
            document_id=doc.id,
            full_text=full_text,
            metadata=extracted,
            run_id=job.run_id,
        )
        doc.classification_state = class_state

        # Step 5: Indexing
        job.step = "indexing"
        db.commit()
        search_service.update_document_index(db, doc.id, owner)
        doc.index_state = "ready"

        # Step 6: Generate thumbnail
        storage_service.generate_thumbnail(doc.id, doc.storage_key, doc.mime_type)

        # Step 7: Finalizing
        job.step = "finalizing"
        doc.processing_state = "ready"
        db.commit()


pipeline = DocumentPipeline()
