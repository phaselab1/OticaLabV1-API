from datetime import UTC, datetime
from typing import Any

from postgrest.exceptions import APIError
from postgrest.types import CountMethod
from supabase import AsyncClient

from app.shared.utils.postgrest import as_row
from app.users.exceptions import UserAlreadyExistsError
from app.users.model import User

TABLE = "users"
UNIQUE_VIOLATION = "23505"


class UserRepository:
    def __init__(self, db: AsyncClient) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> User:
        try:
            response = await self.db.table(TABLE).insert(data).execute()
        except APIError as exc:
            if exc.code == UNIQUE_VIOLATION:
                raise UserAlreadyExistsError(data["email"]) from exc
            raise
        return User.from_row(as_row(response.data[0]))

    async def get_all(self, *, page: int, page_size: int) -> tuple[list[User], int]:
        response = (
            await self.db.table(TABLE)
            .select("*", count=CountMethod.exact)
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execute()
        )
        users = [User.from_row(as_row(row)) for row in response.data]
        return users, response.count or 0

    async def get_by_id(self, user_id: str) -> User | None:
        response = (
            await self.db.table(TABLE)
            .select("*")
            .eq("id", user_id)
            .is_("deleted_at", "null")
            .maybe_single()
            .execute()
        )
        return User.from_row(as_row(response.data)) if response else None

    async def get_by_email(self, email: str) -> User | None:
        response = (
            await self.db.table(TABLE)
            .select("*")
            .eq("email", email)
            .is_("deleted_at", "null")
            .maybe_single()
            .execute()
        )
        return User.from_row(as_row(response.data)) if response else None

    async def update(self, user_id: str, data: dict[str, Any]) -> User | None:
        try:
            response = (
                await self.db.table(TABLE)
                .update(data)
                .eq("id", user_id)
                .is_("deleted_at", "null")
                .execute()
            )
        except APIError as exc:
            if exc.code == UNIQUE_VIOLATION:
                raise UserAlreadyExistsError(data.get("email", "")) from exc
            raise
        return User.from_row(as_row(response.data[0])) if response.data else None

    async def soft_delete(self, user_id: str) -> bool:
        response = (
            await self.db.table(TABLE)
            .update({"deleted_at": datetime.now(UTC).isoformat()})
            .eq("id", user_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return len(response.data) > 0
