from datetime import UTC, datetime

import pytest

from app.auth.exceptions import InvalidCredentialsError
from app.auth.service import AuthService
from app.core.security import decode_access_token, hash_password
from app.users.model import User, UserRole


class FakeUserRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = {u.email: u for u in users}

    async def get_by_email(self, email: str) -> User | None:
        return self.users.get(email)


def _make_user(email: str, password: str) -> User:
    now = datetime.now(UTC)
    return User(
        id="user-1",
        full_name="Ana",
        email=email,
        password_hash=hash_password(password),
        role=UserRole.ATTENDANT,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


async def test_login_with_correct_credentials_returns_valid_token() -> None:
    user = _make_user("ana@example.com", "supersecret")
    service = AuthService(FakeUserRepository([user]))  # type: ignore[arg-type]

    token = await service.login("ana@example.com", "supersecret")

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == user.id


async def test_login_with_wrong_password_raises() -> None:
    user = _make_user("ana@example.com", "supersecret")
    service = AuthService(FakeUserRepository([user]))  # type: ignore[arg-type]

    with pytest.raises(InvalidCredentialsError):
        await service.login("ana@example.com", "wrong-password")


async def test_login_with_unknown_email_raises() -> None:
    service = AuthService(FakeUserRepository([]))  # type: ignore[arg-type]

    with pytest.raises(InvalidCredentialsError):
        await service.login("missing@example.com", "supersecret")
