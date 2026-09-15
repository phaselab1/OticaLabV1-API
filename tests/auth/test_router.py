import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.exceptions import InvalidCredentialsError
from app.main import app


class FakeAuthService:
    async def login(self, email: str, password: str) -> str:
        if email == "ana@example.com" and password == "supersecret":
            return "fake-jwt-token"
        raise InvalidCredentialsError


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_auth_service] = FakeAuthService
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
