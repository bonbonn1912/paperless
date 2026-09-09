from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.folder import DocumentFolder, Folder
from app.services.folders import folder_service


def test_folder_hierarchy_and_cycles(db_session: Session):
    root = folder_service.create_folder(db_session, "user1", "Finanzen")
    sub = folder_service.create_folder(db_session, "user1", "2026", parent_id=root.id)
    sub_sub = folder_service.create_folder(db_session, "user1", "Q1", parent_id=sub.id)

    assert sub.parent_id == root.id
    assert sub_sub.parent_id == sub.id

    # Test cycle: cannot move root into sub_sub
    with pytest.raises(ValueError, match="Cannot move folder into one of its own subfolders"):
        folder_service.update_folder(db_session, "user1", root.id, parent_id=sub_sub.id)

    # Test self-parent
    with pytest.raises(ValueError, match="cannot be its own parent"):
        folder_service.update_folder(db_session, "user1", root.id, parent_id=root.id)


def test_folder_document_association_and_deletion(db_session: Session):
    folder1 = folder_service.create_folder(db_session, "user1", "Ordner A")
    folder2 = folder_service.create_folder(db_session, "user1", "Ordner B")

    doc = Document(
        id="doc-folder-1",
        owner="user1",
        original_name="test.pdf",
        storage_key="test.pdf",
        mime_type="application/pdf",
        file_size=100,
        sha256="sha-f-1",
    )
    db_session.add(doc)
    db_session.commit()

    # Document can be in multiple folders
    folder_service.add_document_to_folder(db_session, "user1", doc.id, folder1.id)
    folder_service.add_document_to_folder(db_session, "user1", doc.id, folder2.id)

    doc_folders = db_session.query(DocumentFolder).filter(DocumentFolder.document_id == doc.id).all()
    assert len(doc_folders) == 2

    # Delete folder1
    folder_service.delete_folder(db_session, "user1", folder1.id)

    # Document still exists!
    reloaded_doc = db_session.query(Document).filter(Document.id == doc.id).first()
    assert reloaded_doc is not None

    # Still associated with folder2
    remaining_folders = db_session.query(DocumentFolder).filter(DocumentFolder.document_id == doc.id).all()
    assert len(remaining_folders) == 1
    assert remaining_folders[0].folder_id == folder2.id
