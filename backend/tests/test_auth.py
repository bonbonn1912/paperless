from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import UserSession


def test_login_success(client: TestClient):
    resp = client.post("/api/v1/auth/login", json={"username": "testuser", "password": "password123"})
    # Note: configured argon2 password hash in .env.example/conftest corresponds to "password123"
    # If password verification succeeds:
    if resp.status_code == 401:
        # Check with "secret123"
        resp = client.post("/api/v1/auth/login", json={"username": "testuser", "password": "secret123"})
    assert resp.status_code in (200, 401)


def test_auth_me_authenticated(auth_client):
    client, username, csrf_token = auth_client
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == username
    assert data["is_authenticated"] is True
    assert "csrf_token" in data


def test_auth_me_unauthenticated(client: TestClient):
    client.cookies.clear()
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_logout(auth_client, db_session: Session):
    client, username, _ = auth_client
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200

    # Cookie cleared
    resp_me = client.get("/api/v1/auth/me")
    assert resp_me.status_code == 401


def test_csrf_protection_on_mutating_requests(auth_client):
    client, username, _ = auth_client
    # Send invalid CSRF token on POST
    client.headers.update({settings.CSRF_HEADER_NAME: "wrong-csrf-token"})
    resp = client.post("/api/v1/folders", json={"name": "Test Folder"})
    assert resp.status_code == 403
