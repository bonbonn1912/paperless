from __future__ import annotations

from typing import List, Optional, Set
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.folder import DocumentFolder, Folder
from app.services.tags import normalize_tag_name


class FolderService:
    def create_folder(
        self,
        db: Session,
        owner: str,
        name: str,
        parent_id: Optional[str] = None,
    ) -> Folder:
        norm_name = normalize_tag_name(name)
        if not norm_name:
            raise ValueError("Folder name cannot be empty.")

        # Check parent ownership
        if parent_id:
            parent = db.query(Folder).filter(Folder.id == parent_id, Folder.owner == owner).first()
            if not parent:
                raise ValueError("Parent folder does not exist or belongs to another user.")

        # Check unique constraint (owner, parent_id, normalized_name)
        existing = (
            db.query(Folder)
            .filter(
                Folder.owner == owner,
                Folder.parent_id == parent_id,
                Folder.normalized_name == norm_name,
            )
            .first()
        )
        if existing:
            return existing

        folder = Folder(
            owner=owner,
            name=name.strip(),
            normalized_name=norm_name,
            parent_id=parent_id,
        )
        db.add(folder)
        db.commit()
        return folder

    def update_folder(
        self,
        db: Session,
        owner: str,
        folder_id: str,
        name: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Folder:
        folder = db.query(Folder).filter(Folder.id == folder_id, Folder.owner == owner).first()
        if not folder:
            raise ValueError("Folder not found.")

        if name is not None:
            norm_name = normalize_tag_name(name)
            if not norm_name:
                raise ValueError("Folder name cannot be empty.")
            folder.name = name.strip()
            folder.normalized_name = norm_name

        if parent_id is not None:
            if parent_id == folder_id:
                raise ValueError("A folder cannot be its own parent.")
            if parent_id != "":
                # Check cycle
                descendant_ids = self.get_descendant_folder_ids(db, owner, folder_id)
                if parent_id in descendant_ids:
                    raise ValueError("Cannot move folder into one of its own subfolders.")
                parent = db.query(Folder).filter(Folder.id == parent_id, Folder.owner == owner).first()
                if not parent:
                    raise ValueError("Target parent folder does not exist.")
                folder.parent_id = parent_id
            else:
                folder.parent_id = None

        db.commit()
        return folder

    def get_descendant_folder_ids(self, db: Session, owner: str, root_folder_id: str) -> Set[str]:
        """Collect all descendant folder IDs recursively."""
        descendants: Set[str] = set()
        queue = [root_folder_id]
        while queue:
            current_id = queue.pop(0)
            children = db.query(Folder.id).filter(Folder.owner == owner, Folder.parent_id == current_id).all()
            for (c_id,) in children:
                if c_id not in descendants:
                    descendants.add(c_id)
                    queue.append(c_id)
        return descendants

    def delete_folder(self, db: Session, owner: str, folder_id: str) -> int:
        """
        Delete a folder and all its subfolders.
        Removes DocumentFolder links, but NEVER touches Document records.
        """
        folder = db.query(Folder).filter(Folder.id == folder_id, Folder.owner == owner).first()
        if not folder:
            raise ValueError("Folder not found.")

        all_to_delete = self.get_descendant_folder_ids(db, owner, folder_id)
        all_to_delete.add(folder_id)

        # Delete document folder associations
        db.query(DocumentFolder).filter(DocumentFolder.folder_id.in_(all_to_delete)).delete(synchronize_session=False)

        # Delete folders
        deleted_count = db.query(Folder).filter(Folder.id.in_(all_to_delete)).delete(synchronize_session=False)
        db.commit()
        return deleted_count

    def add_document_to_folder(self, db: Session, owner: str, document_id: str, folder_id: str) -> None:
        doc = db.query(Document).filter(Document.id == document_id, Document.owner == owner).first()
        folder = db.query(Folder).filter(Folder.id == folder_id, Folder.owner == owner).first()
        if not doc or not folder:
            raise ValueError("Document or folder not found.")

        existing = (
            db.query(DocumentFolder)
            .filter(DocumentFolder.document_id == document_id, DocumentFolder.folder_id == folder_id)
            .first()
        )
        if not existing:
            db.add(DocumentFolder(document_id=document_id, folder_id=folder_id))
            db.commit()

    def remove_document_from_folder(self, db: Session, owner: str, document_id: str, folder_id: str) -> None:
        db.query(DocumentFolder).filter(
            DocumentFolder.document_id == document_id,
            DocumentFolder.folder_id == folder_id,
        ).delete()
        db.commit()


folder_service = FolderService()
