from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Generator, Tuple
import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set test environment
os.environ["APP_ENV"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-key-32-bytes-minimum-ok"
# User "testuser" with password "secret123"
os.environ["APP_USERS_JSON"] = '{"testuser":"$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$RdescudvJCsgqlfreOJAcw"}'

from app.config import settings
from app.db.session import Base, get_db, init_db
from app.main import app
from app.services.auth import create_user_session, generate_csrf_token


@pytest.fixture(scope="session", autouse=True)
def test_data_dir():
    temp_dir = tempfile.TemporaryDirectory()
    settings.DATA_DIR = Path(temp_dir.name)
    settings.ensure_directories()
    yield
    temp_dir.cleanup()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    # Use dedicated test sqlite file
    test_db_file = settings.database_dir / f"test_{tempfile.mktemp(dir='')}.sqlite3"
    engine = create_engine(f"sqlite:///{test_db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    init_db(engine)

    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        if test_db_file.exists():
            test_db_file.unlink(missing_ok=True)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_client(client: TestClient, db_session: Session) -> Tuple[TestClient, str, str]:
    """Client with valid authenticated session cookie and CSRF header."""
    raw_token, session_record = create_user_session(db_session, "testuser")
    csrf_token = generate_csrf_token(raw_token)
    client.cookies.set(settings.SESSION_COOKIE_NAME, raw_token)
    client.headers.update({settings.CSRF_HEADER_NAME: csrf_token})
    return client, "testuser", csrf_token


@pytest.fixture(scope="session")
def sample_pdf_bytes() -> bytes:
    """Create a valid synthetic 2-page PDF."""
    doc = fitz.open()
    # Page 1: Rechnungsnummer & Betrag
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 72), "Musterfirma GmbH\nHauptstr. 1, 10115 Berlin", fontsize=11)
    page1.insert_text((50, 150), "RECHNUNG", fontsize=18)
    page1.insert_text((50, 180), "Rechnungsnummer: RE-2026-0042\nDatum: 15.03.2026", fontsize=11)
    page1.insert_text((50, 250), "Gesamtbetrag: 149,99 EUR\nZahlbar bis: 30.03.2026", fontsize=12)

    # Page 2: Details
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 72), "Position 1: Beratungsleistung 149,99 EUR", fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture(scope="session")
def sample_image_bytes() -> bytes:
    """Create a valid synthetic JPEG image."""
    img = Image.new("RGB", (300, 300), color=(240, 240, 240))
    bio = io.BytesIO()
    img.save(bio, format="JPEG")
    return bio.getvalue()
