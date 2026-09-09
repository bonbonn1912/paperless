from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.folder import DocumentFolder, Folder
from app.schemas.folder import FolderCreate, FolderResponse, FolderUpdate
from app.services.folders import folder_service

router = APIRouter(tags=["folders"])


@router.get("/folders")
def list_folders(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> List[FolderResponse]:
    folders = db.query(Folder).filter(Folder.owner == user).all()

    # Calculate document counts per folder
    counts = dict(
        db.query(DocumentFolder.folder_id, func.count(DocumentFolder.id))
        .group_by(DocumentFolder.folder_id)
        .all()
    )

    # Build response list
    results = [
        FolderResponse(
            id=f.id,
            owner=f.owner,
            name=f.name,
            parent_id=f.parent_id,
            document_count=counts.get(f.id, 0),
            created_at=f.created_at,
        )
        for f in folders
    ]
    return results


@router.post("/folders", status_code=status.HTTP_201_CREATED)
def create_folder(
    req: FolderCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FolderResponse:
    try:
        folder = folder_service.create_folder(db, user, req.name, req.parent_id)
        return FolderResponse(
            id=folder.id,
            owner=folder.owner,
            name=folder.name,
            parent_id=folder.parent_id,
            document_count=0,
            created_at=folder.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/folders/{folder_id}")
def update_folder(
    folder_id: str,
    update: FolderUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FolderResponse:
    try:
        folder = folder_service.update_folder(db, user, folder_id, update.name, update.parent_id)
        return FolderResponse(
            id=folder.id,
            owner=folder.owner,
            name=folder.name,
            parent_id=folder.parent_id,
            document_count=0,
            created_at=folder.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    try:
        deleted_count = folder_service.delete_folder(db, user, folder_id)
        return {"message": "Folder deleted", "deleted_count": deleted_count}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/documents/{document_id}/folders/{folder_id}")
def add_document_to_folder(
    document_id: str,
    folder_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    try:
        folder_service.add_document_to_folder(db, user, document_id, folder_id)
        return {"message": "Document added to folder"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/documents/{document_id}/folders/{folder_id}")
def remove_document_from_folder(
    document_id: str,
    folder_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    folder_service.remove_document_from_folder(db, user, document_id, folder_id)
    return {"message": "Document removed from folder"}
