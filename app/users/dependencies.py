from typing import Annotated, Any

from fastapi import Depends

from app.core.dependencies import SupabaseClient, get_token_payload
from app.core.exceptions import UnauthorizedError
from app.users.model import User
from app.users.repository import UserRepository
from app.users.service import UserService


def get_user_repository(db: SupabaseClient) -> UserRepository:
    return UserRepository(db)


def get_user_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repository)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


async def get_current_user(
    payload: Annotated[dict[str, Any], Depends(get_token_payload)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    user = await repository.get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User not found")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
