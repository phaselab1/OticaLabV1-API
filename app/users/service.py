from app.core.security import hash_password
from app.shared.pagination import Page
from app.users.exceptions import UserNotFoundError
from app.users.model import User
from app.users.repository import UserRepository
from app.users.schema import UserCreate, UserUpdate


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def create(self, data: UserCreate) -> User:
        payload = data.model_dump(mode="json", exclude={"password"})
        payload["password_hash"] = hash_password(data.password)
        return await self.repository.create(payload)

    async def get_all(self, *, page: int, page_size: int) -> Page[User]:
        users, total = await self.repository.get_all(page=page, page_size=page_size)
        return Page(items=users, page=page, page_size=page_size, total=total)

    async def get_by_id(self, user_id: str) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    async def update(self, user_id: str, data: UserUpdate) -> User:
        payload = data.model_dump(mode="json", exclude_unset=True)
        user = await self.repository.update(user_id, payload)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    async def delete(self, user_id: str) -> None:
        deleted = await self.repository.soft_delete(user_id)
        if not deleted:
            raise UserNotFoundError(user_id)
