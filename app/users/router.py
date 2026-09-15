from typing import Annotated

from fastapi import APIRouter, Query, status

from app.shared.pagination import Page
from app.users.dependencies import CurrentUser, UserServiceDep
from app.users.model import User
from app.users.schema import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate, service: UserServiceDep, _current_user: CurrentUser
) -> User:
    return await service.create(data)


@router.get("/", response_model=Page[UserResponse])
async def list_users(
    service: UserServiceDep,
    _current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[User]:
    return await service.get_all(page=page, page_size=page_size)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, service: UserServiceDep, _current_user: CurrentUser) -> User:
    return await service.get_by_id(user_id)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str, data: UserUpdate, service: UserServiceDep, _current_user: CurrentUser
) -> User:
    return await service.update(user_id, data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, service: UserServiceDep, _current_user: CurrentUser) -> None:
    await service.delete(user_id)
