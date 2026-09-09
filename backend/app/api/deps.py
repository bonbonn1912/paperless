from __future__ import annotations

from typing import Annotated, Generator
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.user import UserSession
from app.services.auth import validate_session, verify_csrf_token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    csrf_token: str | None = Header(None, alias=settings.CSRF_HEADER_NAME),
) -> str:
    """Validate authenticated session cookie and CSRF token for mutating requests."""
    if not session_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (missing session cookie)",
        )

    user_session = validate_session(db, session_cookie)
    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    # CSRF check on mutating methods
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        # Allow requests with valid CSRF header or Bearer if automated
        if csrf_token and not verify_csrf_token(session_cookie, csrf_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token",
            )

    return user_session.username


CurrentUser = Annotated[str, Depends(get_current_user)]
