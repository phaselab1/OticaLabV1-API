from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.exceptions import InvalidCredentialsError
from app.main import app
from app.users.dependencies import get_current_user
from app.users.model import User, UserRole


class FakeAuthService:
    async def login(self, email: str, password: str) -> str:
        if email == "ana@example.com" and password == "supersecret":
            return "fake-jwt-token"
        raise InvalidCredentialsError


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_auth_service] = FakeAuthService
    now = datetime.now(UTC)
    app.dependency_overrides[get_current_user] = lambda: User(
        id="user-1",
        full_name="Ana Silva",
        email="ana@example.com",
        password_hash="not-returned",
        role=UserRole.ATTENDANT,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_login_success(client: TestClient) -> None:
    response = client.post(
        "/auth/login", json={"email": "ana@example.com", "password": "supersecret"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "fake-jwt-token"
    assert body["token_type"] == "bearer"


def test_login_invalid_credentials(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": "ana@example.com", "password": "wrong"})

    assert response.status_code == 401


def test_get_authenticated_profile(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "user-1"
    assert body["full_name"] == "Ana Silva"
    assert body["email"] == "ana@example.com"
    assert body["role"] == "attendant"
    assert "password_hash" not in body
