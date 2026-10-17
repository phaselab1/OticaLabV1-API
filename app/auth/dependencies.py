from typing import Annotated

from fastapi import Depends

from app.auth.repository import LoginAttemptRepository
from app.auth.service import AuthService
from app.core.dependencies import SupabaseClient
from app.users.dependencies import get_user_repository
from app.users.repository import UserRepository


def get_login_attempt_repository(db: SupabaseClient) -> LoginAttemptRepository:
    return LoginAttemptRepository(db)


def get_auth_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    login_attempt_repository: Annotated[
        LoginAttemptRepository, Depends(get_login_attempt_repository)
    ],
) -> AuthService:
    return AuthService(user_repository, login_attempt_repository)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
