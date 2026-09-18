from datetime import UTC, datetime, timedelta

import pytest

from app.auth.exceptions import InvalidCredentialsError, TooManyLoginAttemptsError
from app.auth.service import AuthService
from app.core.security import decode_access_token, hash_password
from app.users.model import User, UserRole


class FakeUserRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = {u.email: u for u in users}

    async def get_by_email(self, email: str) -> User | None:
        return self.users.get(email)


class FakeLoginAttemptRepository:
    def __init__(self) -> None:
        self.attempts: list[tuple[str, bool]] = []

    async def count_recent_failures(self, email: str, *, window: timedelta) -> int:
        return sum(
            1
            for attempted_email, success in self.attempts
            if attempted_email == email and not success
        )

    async def record(self, email: str, *, success: bool) -> None:
        self.attempts.append((email, success))


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
    service = AuthService(FakeUserRepository([user]), FakeLoginAttemptRepository())  # type: ignore[arg-type]

    token = await service.login("ana@example.com", "supersecret")

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == user.id
    assert payload["role"] == user.role.value


async def test_login_with_wrong_password_raises() -> None:
    user = _make_user("ana@example.com", "supersecret")
    service = AuthService(FakeUserRepository([user]), FakeLoginAttemptRepository())  # type: ignore[arg-type]

    with pytest.raises(InvalidCredentialsError):
        await service.login("ana@example.com", "wrong-password")


async def test_login_with_unknown_email_raises() -> None:
    service = AuthService(FakeUserRepository([]), FakeLoginAttemptRepository())  # type: ignore[arg-type]

    with pytest.raises(InvalidCredentialsError):
        await service.login("missing@example.com", "supersecret")


async def test_login_locked_out_after_too_many_failures() -> None:
    user = _make_user("ana@example.com", "supersecret")
    login_attempt_repository = FakeLoginAttemptRepository()
    service = AuthService(FakeUserRepository([user]), login_attempt_repository)  # type: ignore[arg-type]

    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            await service.login("ana@example.com", "wrong-password")

    with pytest.raises(TooManyLoginAttemptsError):
        await service.login("ana@example.com", "supersecret")
