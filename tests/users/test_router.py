from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import app
from app.shared.pagination import Page
from app.users.dependencies import get_current_user, get_user_service
from app.users.exceptions import UserNotFoundError
from app.users.model import User, UserRole
from app.users.schema import UserCreate, UserUpdate


def _fake_current_user(role: UserRole = UserRole.SUPER_ADMIN) -> User:
    now = datetime.now(UTC)
    return User(
        id="user-1",
        full_name="Admin",
        email="admin@example.com",
        password_hash="hash",
        role=role,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


class FakeUserService:
    def __init__(self) -> None:
        self.rows: dict[str, User] = {}

    async def create(self, data: UserCreate) -> User:
        now = datetime.now(UTC)
        user = User(
            id=str(len(self.rows) + 1),
            full_name=data.full_name,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.rows[user.id] = user
        return user

    async def get_all(self, **_: object) -> Page[User]:
        items = list(self.rows.values())
        return Page(items=items, page=1, page_size=20, total=len(items))

    async def get_by_id(self, user_id: str) -> User:
        user = self.rows.get(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    async def update(self, user_id: str, data: UserUpdate) -> User:
        user = await self.get_by_id(user_id)
        updated = replace(user, **data.model_dump(exclude_unset=True))
        self.rows[user_id] = updated
        return updated

    async def delete(self, user_id: str) -> None:
        await self.get_by_id(user_id)
        del self.rows[user_id]


@pytest.fixture
def client() -> TestClient:
    fake_service = FakeUserService()
    app.dependency_overrides[get_user_service] = lambda: fake_service
    app.dependency_overrides[get_current_user] = _fake_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_user_requires_auth(client: TestClient) -> None:
    del app.dependency_overrides[get_current_user]

    response = client.post(
        "/users/",
        json={"full_name": "Ana", "email": "ana@example.com", "password": "supersecret"},
    )

    assert response.status_code == 401


def test_create_user_as_attendant_forbidden(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _fake_current_user(UserRole.ATTENDANT)

    response = client.post(
        "/users/",
        json={"full_name": "Ana", "email": "ana@example.com", "password": "supersecret"},
    )

    assert response.status_code == 403


def test_create_user(client: TestClient) -> None:
    response = client.post(
        "/users/",
        json={"full_name": "Ana", "email": "ana@example.com", "password": "supersecret"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ana@example.com"
    assert "password" not in body
    assert "password_hash" not in body


def test_full_crud_flow(client: TestClient) -> None:
    created = client.post(
        "/users/",
        json={"full_name": "Bruno", "email": "bruno@example.com", "password": "supersecret"},
    ).json()
    user_id = created["id"]

    got = client.get(f"/users/{user_id}")
    assert got.status_code == 200

    updated = client.put(f"/users/{user_id}", json={"full_name": "Bruno Souza"})
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Bruno Souza"

    deleted = client.delete(f"/users/{user_id}")
    assert deleted.status_code == 204

    after_delete = client.get(f"/users/{user_id}")
    assert after_delete.status_code == 404
