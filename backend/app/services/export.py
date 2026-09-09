from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict
from sqlalchemy.orm import Session

from app.config import settings
from app.models.base import utc_now
from app.models.document import Document, DocumentAsset, DocumentFieldOverride
from app.models.folder import DocumentFolder, Folder
from app.models.tag import DocumentTag, Tag


class ExportService:
    def export_user_data(self, db: Session, owner: str) -> str:
        """Export all user documents, assets, and metadata to exports/<uuid>/."""
        export_id = str(uuid.uuid4())
        dest_dir = settings.exports_dir / export_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        docs_dir = dest_dir / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)

        docs = db.query(Document).filter(Document.owner == owner, Document.deleted_at.is_(None)).all()
        manifest_docs = []

        for doc in docs:
            # Copy main file
            src_file = settings.documents_dir / doc.storage_key
            if src_file.exists():
                shutil.copy2(str(src_file), str(docs_dir / doc.storage_key))

            # Fetch tags
            tags = (
                db.query(Tag.name)
                .join(DocumentTag, DocumentTag.tag_id == Tag.id)
                .filter(DocumentTag.document_id == doc.id)
                .all()
            )

            # Fetch folders
            folders = (
                db.query(Folder.name)
                .join(DocumentFolder, DocumentFolder.folder_id == Folder.id)
                .filter(DocumentFolder.document_id == doc.id)
                .all()
            )

            # Fetch overrides
            overrides = (
                db.query(DocumentFieldOverride)
                .filter(DocumentFieldOverride.document_id == doc.id)
                .all()
            )

            manifest_docs.append({
                "id": doc.id,
                "original_name": doc.original_name,
                "storage_key": doc.storage_key,
                "mime_type": doc.mime_type,
                "file_size": doc.file_size,
                "sha256": doc.sha256,
                "title": doc.title,
                "sender": doc.sender,
                "document_date": doc.document_date.isoformat() if doc.document_date else None,
                "due_date": doc.due_date.isoformat() if doc.due_date else None,
                "amount_cents": doc.amount,
                "currency": doc.currency,
                "source": doc.source,
                "tags": [t[0] for t in tags],
                "folders": [f[0] for f in folders],
                "field_overrides": {o.field_name: o.value for o in overrides},
                "created_at": doc.created_at.isoformat(),
            })

        manifest = {
            "export_id": export_id,
            "owner": owner,
            "exported_at": utc_now().isoformat(),
            "document_count": len(manifest_docs),
            "documents": manifest_docs,
        }

        with open(dest_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        return export_id


export_service = ExportService()
