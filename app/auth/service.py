from app.auth.exceptions import InvalidCredentialsError
from app.core.security import create_access_token, verify_password
from app.users.repository import UserRepository


class AuthService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def login(self, email: str, password: str) -> str:
        user = await self.user_repository.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError

        return create_access_token(subject=user.id)
