from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.core.exceptions import register_exception_handlers


def _make_client(code: str) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise APIError({"message": "boom", "code": code, "hint": None, "details": None})

    return TestClient(app, raise_server_exceptions=False)


def test_invalid_uuid_returns_404() -> None:
    client = _make_client("22P02")
    response = client.get("/boom")
    assert response.status_code == 404
    assert response.json() == {"detail": "Resource not found"}


def test_foreign_key_violation_returns_404() -> None:
    client = _make_client("23503")
    response = client.get("/boom")
    assert response.status_code == 404
    assert response.json() == {"detail": "Referenced resource not found"}


def test_business_rule_violation_returns_400_with_message() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise APIError(
            {
                "message": "unit X does not belong to company Y",
                "code": "P0001",
                "hint": None,
                "details": None,
            }
        )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 400
    assert response.json() == {"detail": "unit X does not belong to company Y"}


def test_unexpected_postgrest_error_returns_generic_500() -> None:
    client = _make_client("XX000")
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
