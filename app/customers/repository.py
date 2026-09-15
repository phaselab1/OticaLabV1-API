from datetime import UTC, datetime
from typing import Any

from postgrest.exceptions import APIError
from postgrest.types import CountMethod
from supabase import AsyncClient

from app.customers.exceptions import CustomerAlreadyExistsError
from app.customers.model import Customer
from app.shared.utils.postgrest import as_row

TABLE = "customers"
UNIQUE_VIOLATION = "23505"


class CustomerRepository:
    def __init__(self, db: AsyncClient) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> Customer:
        try:
            response = await self.db.table(TABLE).insert(data).execute()
        except APIError as exc:
            if exc.code == UNIQUE_VIOLATION:
                raise CustomerAlreadyExistsError(data["full_name"], data["date_of_birth"]) from exc
            raise
        return Customer.from_row(as_row(response.data[0]))

    async def get_all(self, *, page: int, page_size: int) -> tuple[list[Customer], int]:
        response = (
            await self.db.table(TABLE)
            .select("*", count=CountMethod.exact)
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execute()
        )
        customers = [Customer.from_row(as_row(row)) for row in response.data]
        return customers, response.count or 0

    async def get_by_id(self, customer_id: str) -> Customer | None:
        response = (
            await self.db.table(TABLE)
            .select("*")
            .eq("id", customer_id)
            .is_("deleted_at", "null")
            .maybe_single()
            .execute()
        )
        return Customer.from_row(as_row(response.data)) if response else None

    async def update(self, customer_id: str, data: dict[str, Any]) -> Customer | None:
        try:
            response = (
                await self.db.table(TABLE)
                .update(data)
                .eq("id", customer_id)
                .is_("deleted_at", "null")
                .execute()
            )
        except APIError as exc:
            if exc.code == UNIQUE_VIOLATION:
                raise CustomerAlreadyExistsError(
                    data.get("full_name", ""), data.get("date_of_birth", "")
                ) from exc
            raise
        return Customer.from_row(as_row(response.data[0])) if response.data else None

    async def soft_delete(self, customer_id: str) -> bool:
        response = (
            await self.db.table(TABLE)
            .update({"deleted_at": datetime.now(UTC).isoformat()})
            .eq("id", customer_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return len(response.data) > 0
