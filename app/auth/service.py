from datetime import timedelta

from app.auth.exceptions import InvalidCredentialsError, TooManyLoginAttemptsError
from app.auth.repository import LoginAttemptRepository
from app.core.security import DUMMY_PASSWORD_HASH, create_access_token, verify_password
from app.users.repository import UserRepository

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW = timedelta(minutes=15)


class AuthService:
    def __init__(
        self, user_repository: UserRepository, login_attempt_repository: LoginAttemptRepository
    ) -> None:
        self.user_repository = user_repository
        self.login_attempt_repository = login_attempt_repository

    async def login(self, email: str, password: str) -> str:
        recent_failures = await self.login_attempt_repository.count_recent_failures(
            email, window=LOCKOUT_WINDOW
        )
        if recent_failures >= MAX_FAILED_ATTEMPTS:
            raise TooManyLoginAttemptsError

        user = await self.user_repository.get_by_email(email)

        # Always run bcrypt, even for a nonexistent user, so response time
        # doesn't reveal whether the email is registered.
        password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
        password_valid = verify_password(password, password_hash)

        success = user is not None and password_valid
        await self.login_attempt_repository.record(email, success=success)

        if user is None or not password_valid:
            raise InvalidCredentialsError

        return create_access_token(subject=user.id)
