from typing import Annotated

from fastapi import Depends

from app.auth.service import AuthService
from app.users.dependencies import get_user_repository
from app.users.repository import UserRepository


def get_auth_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(user_repository)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
