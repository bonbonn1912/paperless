from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.config import settings as app_settings
from app.db.session import get_db
from app.models.user import UserSettings
from app.schemas.settings import CapabilitiesResponse, SettingsResponse, SettingsUpdate

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsResponse)
def get_user_settings(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> SettingsResponse:
    user_set = db.query(UserSettings).filter(UserSettings.owner == user).first()
    if not user_set:
        user_set = UserSettings(
            owner=user,
            preferences={
                "ocr_languages": app_settings.OCR_LANGUAGES,
                "ocr_dpi": app_settings.OCR_DPI,
            },
            pinned_tabs=["Rechnungen", "Verträge", "Belege"],
        )
        db.add(user_set)
        db.commit()

    return SettingsResponse(
        owner=user_set.owner,
        preferences=user_set.preferences,
        pinned_tabs=user_set.pinned_tabs,
    )


@router.patch("/settings", response_model=SettingsResponse)
def update_user_settings(
    update: SettingsUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> SettingsResponse:
    user_set = db.query(UserSettings).filter(UserSettings.owner == user).first()
    if not user_set:
        user_set = UserSettings(owner=user)
        db.add(user_set)

    if update.preferences is not None:
        curr = dict(user_set.preferences)
        curr.update(update.preferences)
        user_set.preferences = curr

    if update.pinned_tabs is not None:
        user_set.pinned_tabs = update.pinned_tabs

    db.commit()
    return SettingsResponse(
        owner=user_set.owner,
        preferences=user_set.preferences,
        pinned_tabs=user_set.pinned_tabs,
    )


@router.get("/system/capabilities", response_model=CapabilitiesResponse)
def get_system_capabilities(user: CurrentUser) -> CapabilitiesResponse:
    return CapabilitiesResponse(
        max_upload_mb=app_settings.MAX_UPLOAD_MB,
        max_batch_files=app_settings.MAX_BATCH_FILES,
        upload_concurrency=app_settings.UPLOAD_CONCURRENCY,
        status_max_items=app_settings.STATUS_MAX_ITEMS,
        max_capture_pages=app_settings.MAX_CAPTURE_PAGES,
        max_capture_total_mb=app_settings.MAX_CAPTURE_TOTAL_MB,
        max_assembled_pdf_mb=app_settings.MAX_ASSEMBLED_PDF_MB,
        heavy_job_concurrency=app_settings.HEAVY_JOB_CONCURRENCY,
        heavy_cpu_limit=app_settings.HEAVY_CPU_LIMIT,
        heavy_memory_mb=app_settings.HEAVY_MEMORY_MB,
        supported_mimes=["application/pdf", "image/jpeg", "image/png", "image/webp", "image/heic"],
        available_ocr_languages=["deu", "eng", "fra", "spa", "ita"],
    )
