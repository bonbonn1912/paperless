from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import UserSession, UserSettings
from app.models.base import utc_now

ph = PasswordHasher()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against an Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def hash_token(token: str) -> str:
    """Hash session token with SHA-256 before storing in SQLite."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_session_token() -> str:
    """Generate cryptographically secure 32-byte URL-safe token."""
    return secrets.token_urlsafe(32)


def generate_csrf_token(session_token: str) -> str:
    """Generate CSRF token bound to the session token and secret key."""
    h = hashlib.sha256((session_token + settings.SECRET_KEY).encode("utf-8"))
    return h.hexdigest()


def verify_csrf_token(session_token: str, csrf_token: str) -> bool:
    """Verify CSRF token matching the session."""
    expected = generate_csrf_token(session_token)
    return secrets.compare_digest(expected, csrf_token)


def create_user_session(db: Session, username: str) -> Tuple[str, UserSession]:
    """Create a new authenticated session for a user."""
    raw_token = generate_session_token()
    token_hash = hash_token(raw_token)
    now = utc_now()
    expires_at = now + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)

    session_record = UserSession(
        session_token_hash=token_hash,
        username=username,
        credential_version=1,
        expires_at=expires_at,
        last_active_at=now,
        revoked=False,
    )
    db.add(session_record)

    # Ensure user settings record exists
    user_settings = db.query(UserSettings).filter(UserSettings.owner == username).first()
    if not user_settings:
        user_settings = UserSettings(
            owner=username,
            preferences={
                "ocr_languages": settings.OCR_LANGUAGES,
                "ocr_dpi": settings.OCR_DPI,
            },
            pinned_tabs=["Rechnungen", "Verträge", "Belege"],
        )
        db.add(user_settings)

    db.commit()
    return raw_token, session_record


def validate_session(db: Session, raw_token: str) -> Optional[UserSession]:
    """Validate raw session token and check expiration and idle timeout."""
    if not raw_token:
        return None

    token_hash = hash_token(raw_token)
    session_record = db.query(UserSession).filter(
        UserSession.session_token_hash == token_hash,
        UserSession.revoked == False,
    ).first()

    if not session_record:
        return None

    from app.models.base import to_utc
    now = utc_now()
    # Check absolute expiration
    if to_utc(session_record.expires_at) < now:
        session_record.revoked = True
        db.commit()
        return None

    # Check idle timeout
    if to_utc(session_record.last_active_at) + timedelta(seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS) < now:
        session_record.revoked = True
        db.commit()
        return None

    # Verify user is still configured in APP_USERS_JSON
    configured_users = settings.get_users()
    if session_record.username not in configured_users:
        session_record.revoked = True
        db.commit()
        return None

    # Update last_active_at periodically (e.g. if > 60s passed)
    if (now - to_utc(session_record.last_active_at)).total_seconds() > 60:
        session_record.last_active_at = now
        db.commit()

    return session_record


def revoke_session(db: Session, raw_token: str) -> None:
    """Revoke a session by token hash."""
    if not raw_token:
        return
    token_hash = hash_token(raw_token)
    session_record = db.query(UserSession).filter(UserSession.session_token_hash == token_hash).first()
    if session_record:
        session_record.revoked = True
        db.commit()
