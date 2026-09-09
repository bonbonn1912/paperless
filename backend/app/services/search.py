from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentPage
from app.models.folder import DocumentFolder
from app.models.tag import DocumentTag, Tag
from app.services.folders import folder_service


def sanitize_fts5_query(query_str: str) -> str:
    """
    Sanitize user input for SQLite FTS5 query.
    Extracts alphanumeric words and formats them safely with prefix matching.
    """
    if not query_str:
        return ""

    # Split into words/tokens
    raw_tokens = re.findall(r"\b[\w\-]+\b", query_str, re.UNICODE)
    if not raw_tokens:
        return ""

    escaped_tokens = []
    for token in raw_tokens:
        # Strip internal quotes
        cleaned = token.replace('"', "")
        if cleaned:
            # Suffix with * for prefix search
            escaped_tokens.append(f'"{cleaned}"*')

    return " AND ".join(escaped_tokens)


class SearchService:
    def update_document_index(
        self,
        db: Session,
        document_id: str,
        owner: str,
    ) -> None:
        """Update FTS5 index for a document from pages, metadata, and tags."""
        doc = db.query(Document).filter(Document.id == document_id, Document.owner == owner).first()
        if not doc or doc.deleted_at is not None:
            # Remove from FTS5 if deleted
            db.execute(
                text("DELETE FROM search_documents WHERE document_id = :doc_id"),
                {"doc_id": document_id},
            )
            db.commit()
            return

        # Aggregate text from all pages
        pages = (
            db.query(DocumentPage)
            .filter(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
            .all()
        )
        content_text = "\n".join([p.extracted_text for p in pages if p.extracted_text])

        # Aggregate tag names and aliases
        doc_tags = (
            db.query(Tag.name)
            .join(DocumentTag, DocumentTag.tag_id == Tag.id)
            .filter(DocumentTag.document_id == document_id)
            .all()
        )
        tag_str = " ".join([t[0] for t in doc_tags])

        # Delete existing entry and insert fresh
        db.execute(
            text("DELETE FROM search_documents WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )
        db.execute(
            text(
                """
                INSERT INTO search_documents(document_id, owner, content, title, original_name, sender, tag_names)
                VALUES (:doc_id, :owner, :content, :title, :original_name, :sender, :tag_names)
                """
            ),
            {
                "doc_id": document_id,
                "owner": owner,
                "content": content_text,
                "title": doc.title or "",
                "original_name": doc.original_name or "",
                "sender": doc.sender or "",
                "tag_names": tag_str,
            },
        )
        db.commit()

    def search_documents(
        self,
        db: Session,
        owner: str,
        query: Optional[str] = None,
        tag_ids: Optional[List[str]] = None,
        tag_mode: str = "any",  # any | all
        folder_id: Optional[str] = None,
        include_descendants: bool = True,
        classification_state: Optional[str] = None,
        processing_state: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Document], int, Dict[str, str]]:
        """
        Global search combining SQLite FTS5 with metadata, folder, and tag filters.
        Returns: (documents, total_count, snippets_dict {doc_id: snippet})
        """
        snippets: Dict[str, str] = {}
        fts_doc_ids: Optional[List[str]] = None

        if query and query.strip():
            fts_q = sanitize_fts5_query(query)
            if fts_q:
                fts_sql = text(
                    """
                    SELECT document_id, snippet(search_documents, 2, '<b>', '</b>', '...', 15) as snip
                    FROM search_documents
                    WHERE search_documents MATCH :query AND owner = :owner
                    ORDER BY bm25(search_documents)
                    LIMIT 200
                    """
                )
                rows = db.execute(fts_sql, {"query": fts_q, "owner": owner}).fetchall()
                fts_doc_ids = [r[0] for r in rows]
                snippets = {r[0]: r[1] for r in rows}
                if not fts_doc_ids:
                    return [], 0, {}

        # Base query for Document
        q = db.query(Document).filter(
            Document.owner == owner,
            Document.deleted_at.is_(None),
        )

        if fts_doc_ids is not None:
            q = q.filter(Document.id.in_(fts_doc_ids))

        if classification_state:
            q = q.filter(Document.classification_state == classification_state)

        if processing_state:
            q = q.filter(Document.processing_state == processing_state)

        if date_from:
            q = q.filter(Document.document_date >= date_from)

        if date_to:
            q = q.filter(Document.document_date <= date_to)

        # Folder filtering
        if folder_id:
            target_folder_ids = {folder_id}
            if include_descendants:
                descendants = folder_service.get_descendant_folder_ids(db, owner, folder_id)
                target_folder_ids.update(descendants)

            q = q.join(DocumentFolder, DocumentFolder.document_id == Document.id).filter(
                DocumentFolder.folder_id.in_(target_folder_ids)
            )

        # Tag filtering
        if tag_ids:
            if tag_mode == "all":
                for t_id in tag_ids:
                    subq = (
                        db.query(DocumentTag.document_id)
                        .filter(DocumentTag.tag_id == t_id)
                        .subquery()
                    )
                    q = q.filter(Document.id.in_(subq))
            else:  # any
                q = q.join(DocumentTag, DocumentTag.document_id == Document.id).filter(
                    DocumentTag.tag_id.in_(tag_ids)
                )

        total_count = q.distinct().count()

        # Sort order: if FTS active, preserve FTS ranking order, otherwise created_at desc
        if fts_doc_ids:
            all_docs = {d.id: d for d in q.distinct().all()}
            ordered_docs = [all_docs[did] for did in fts_doc_ids if did in all_docs]
            docs = ordered_docs[offset : offset + limit]
        else:
            docs = (
                q.distinct()
                .order_by(Document.created_at.desc(), Document.id.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

        return docs, total_count, snippets

    def search_in_document(
        self,
        db: Session,
        owner: str,
        document_id: str,
        term: str,
    ) -> List[Dict[str, Any]]:
        """
        Search inside a specific document for word highlighting in the viewer.
        Matches against extracted text and computes bounding box hits from word_boxes.
        """
        doc = db.query(Document).filter(Document.id == document_id, Document.owner == owner).first()
        if not doc or not term:
            return []

        clean_term = term.strip().casefold()
        pages = (
            db.query(DocumentPage)
            .filter(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
            .all()
        )

        results: List[Dict[str, Any]] = []
        for p in pages:
            page_text = p.extracted_text or ""
            page_text_lower = page_text.casefold()

            # Find occurrences in text
            start_pos = 0
            while True:
                idx = page_text_lower.find(clean_term, start_pos)
                if idx == -1:
                    break

                matched_str = page_text[idx : idx + len(clean_term)]
                # Find matching word boxes if available
                boxes = []
                if p.word_boxes:
                    for wb in p.word_boxes:
                        w_text = wb.get("text", "").casefold()
                        if clean_term in w_text or w_text in clean_term:
                            boxes.append({
                                "x0": wb.get("x0", 0),
                                "y0": wb.get("y0", 0),
                                "x1": wb.get("x1", 0),
                                "y1": wb.get("y1", 0),
                            })

                results.append({
                    "page_number": p.page_number,
                    "matched_text": matched_str,
                    "offset_start": idx,
                    "offset_end": idx + len(clean_term),
                    "boxes": boxes,
                    "width": p.width,
                    "height": p.height,
                })
                start_pos = idx + len(clean_term)

        return results


search_service = SearchService()
