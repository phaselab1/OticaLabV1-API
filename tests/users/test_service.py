from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.security import verify_password
from app.users.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.users.model import User
from app.users.schema import UserCreate, UserUpdate
from app.users.service import UserService


class FakeUserRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def create(self, data: dict[str, Any]) -> User:
        for row in self.rows.values():
            if row["deleted_at"] is None and row["email"] == data["email"]:
                raise UserAlreadyExistsError(data["email"])

        user_id = str(len(self.rows) + 1)
        now = datetime.now(UTC).isoformat()
        row = {"id": user_id, "created_at": now, "updated_at": now, "deleted_at": None, **data}
        self.rows[user_id] = row
        return User.from_row(row)

    async def get_all(self, *, page: int, page_size: int) -> tuple[list[User], int]:
        active = [r for r in self.rows.values() if r["deleted_at"] is None]
        start = (page - 1) * page_size
        return [User.from_row(r) for r in active[start : start + page_size]], len(active)

    async def get_by_id(self, user_id: str) -> User | None:
        row = self.rows.get(user_id)
        if row is None or row["deleted_at"] is not None:
            return None
        return User.from_row(row)

    async def get_by_email(self, email: str) -> User | None:
        for row in self.rows.values():
            if row["deleted_at"] is None and row["email"] == email:
                return User.from_row(row)
        return None

    async def update(self, user_id: str, data: dict[str, Any]) -> User | None:
        row = self.rows.get(user_id)
        if row is None or row["deleted_at"] is not None:
            return None
        row.update(data)
        return User.from_row(row)

    async def soft_delete(self, user_id: str) -> bool:
        row = self.rows.get(user_id)
        if row is None or row["deleted_at"] is not None:
            return False
        row["deleted_at"] = datetime.now(UTC).isoformat()
        return True


@pytest.fixture
def service() -> UserService:
    return UserService(FakeUserRepository())  # type: ignore[arg-type]


async def test_create_hashes_password(service: UserService) -> None:
    created = await service.create(
        UserCreate(full_name="Ana", email="ana@example.com", password="supersecret")
    )

    assert created.password_hash != "supersecret"
    assert verify_password("supersecret", created.password_hash)


async def test_create_duplicate_email_raises(service: UserService) -> None:
    data = UserCreate(full_name="Ana", email="ana@example.com", password="supersecret")
    await service.create(data)

    with pytest.raises(UserAlreadyExistsError):
        await service.create(data)


async def test_get_by_id_missing_raises_not_found(service: UserService) -> None:
    with pytest.raises(UserNotFoundError):
        await service.get_by_id("missing")


async def test_delete_then_get_by_id_raises_not_found(service: UserService) -> None:
    created = await service.create(
        UserCreate(full_name="Bruno", email="bruno@example.com", password="supersecret")
    )

    await service.delete(created.id)

    with pytest.raises(UserNotFoundError):
        await service.get_by_id(created.id)


async def test_update_missing_user_raises_not_found(service: UserService) -> None:
    with pytest.raises(UserNotFoundError):
        await service.update("missing", UserUpdate(full_name="X"))
