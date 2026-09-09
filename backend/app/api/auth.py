from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.schemas.auth import LoginRequest, UserInfo
from app.services.auth import (
    create_user_session,
    generate_csrf_token,
    revoke_session,
    validate_session,
    verify_password,
)
from app.services.tags import tag_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(
    req: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    configured_users = settings.get_users()
    if req.username not in configured_users:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    hashed_pw = configured_users[req.username]
    if not verify_password(req.password, hashed_pw):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    # Create session
    raw_token, session_record = create_user_session(db, req.username)
    csrf_token = generate_csrf_token(raw_token)

    # Initialize default tags for user if not yet initialized
    tag_service.ensure_default_tags(db, req.username)

    # Set secure HttpOnly cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=settings.APP_ENV == "production",
    )

    return {
        "username": req.username,
        "csrf_token": csrf_token,
        "message": "Login successful",
    }


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
) -> dict:
    if session_cookie:
        revoke_session(db, session_cookie)
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    return {"message": "Logged out successfully"}


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
) -> dict:
    if not session_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    session_record = validate_session(db, session_cookie)
    if not session_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")

    csrf_token = generate_csrf_token(session_cookie)
    return {
        "username": session_record.username,
        "is_authenticated": True,
        "csrf_token": csrf_token,
    }
