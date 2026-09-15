from datetime import UTC, datetime
from typing import Any

from postgrest.types import CountMethod
from supabase import AsyncClient

from app.appointments.model import Appointment, AppointmentStatus
from app.shared.utils.postgrest import as_row

TABLE = "appointments"


class AppointmentRepository:
    def __init__(self, db: AsyncClient) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> Appointment:
        response = await self.db.table(TABLE).insert(data).execute()
        return Appointment.from_row(as_row(response.data[0]))

    async def get_all(
        self,
        *,
        page: int,
        page_size: int,
        customer_id: str | None = None,
        status: AppointmentStatus | None = None,
    ) -> tuple[list[Appointment], int]:
        query = self.db.table(TABLE).select("*", count=CountMethod.exact).is_("deleted_at", "null")

        if customer_id is not None:
            query = query.eq("customer_id", customer_id)
        if status is not None:
            query = query.eq("status", status.value)

        response = await (
            query.order("scheduled_at", desc=False)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execute()
        )
        appointments = [Appointment.from_row(as_row(row)) for row in response.data]
        return appointments, response.count or 0

    async def get_by_id(self, appointment_id: str) -> Appointment | None:
        response = (
            await self.db.table(TABLE)
            .select("*")
            .eq("id", appointment_id)
            .is_("deleted_at", "null")
            .maybe_single()
            .execute()
        )
        return Appointment.from_row(as_row(response.data)) if response else None

    async def update(self, appointment_id: str, data: dict[str, Any]) -> Appointment | None:
        response = (
            await self.db.table(TABLE)
            .update(data)
            .eq("id", appointment_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return Appointment.from_row(as_row(response.data[0])) if response.data else None

    async def soft_delete(self, appointment_id: str) -> bool:
        response = (
            await self.db.table(TABLE)
            .update({"deleted_at": datetime.now(UTC).isoformat()})
            .eq("id", appointment_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return len(response.data) > 0
