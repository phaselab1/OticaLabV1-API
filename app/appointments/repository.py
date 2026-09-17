from datetime import UTC, datetime
from typing import Any

from postgrest.exceptions import APIError
from postgrest.types import CountMethod
from supabase import AsyncClient

from app.appointments.exceptions import AppointmentAlreadyExistsError
from app.appointments.model import Appointment, AppointmentHistoryEntry, AppointmentStatus
from app.shared.utils.postgrest import as_row, as_rows

TABLE = "appointments"
HISTORY_TABLE = "appointment_history"
UPDATE_WITH_HISTORY_FN = "update_appointment_with_history"
APPOINTMENT_NOT_FOUND = "P0002"
UNIQUE_VIOLATION = "23505"


class AppointmentRepository:
    def __init__(self, db: AsyncClient) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> Appointment:
        try:
            response = await self.db.table(TABLE).insert(data).execute()
        except APIError as exc:
            if exc.code == UNIQUE_VIOLATION:
                customer_id = data.get("customer_id")
                subject = f"Customer {customer_id}" if customer_id else data["lead_full_name"]
                raise AppointmentAlreadyExistsError(subject, data["scheduled_at"]) from exc
            raise
        return Appointment.from_row(as_row(response.data[0]))

    async def get_all(
        self,
        *,
        page: int,
        page_size: int,
        company_id: str | None = None,
        company_unit_id: str | None = None,
        customer_id: str | None = None,
        status: AppointmentStatus | None = None,
    ) -> tuple[list[Appointment], int]:
        query = self.db.table(TABLE).select("*", count=CountMethod.exact).is_("deleted_at", "null")

        if company_id is not None:
            query = query.eq("company_id", company_id)
        if company_unit_id is not None:
            query = query.eq("company_unit_id", company_unit_id)
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

    async def update_with_history(
        self,
        appointment_id: str,
        changed_by_user_id: str,
        *,
        scheduled_at: str | None,
        status: str | None,
        notes: str | None,
        notes_provided: bool,
        customer_id: str | None = None,
    ) -> Appointment | None:
        try:
            response = await self.db.rpc(
                UPDATE_WITH_HISTORY_FN,
                {
                    "p_appointment_id": appointment_id,
                    "p_changed_by_user_id": changed_by_user_id,
                    "p_new_scheduled_at": scheduled_at,
                    "p_new_status": status,
                    "p_new_notes": notes,
                    "p_notes_provided": notes_provided,
                    "p_customer_id": customer_id,
                },
            ).execute()
        except APIError as exc:
            if exc.code == APPOINTMENT_NOT_FOUND:
                return None
            raise
        rows = as_rows(response.data)
        return Appointment.from_row(rows[0]) if rows else None

    async def update_lead_info(
        self,
        appointment_id: str,
        changed_by_user_id: str,
        *,
        lead_full_name: str | None = None,
        lead_phone: str | None = None,
        lead_phone_provided: bool = False,
    ) -> Appointment | None:
        update_data: dict[str, Any] = {
            "updated_by_user_id": changed_by_user_id,
        }
        if lead_full_name is not None:
            update_data["lead_full_name"] = lead_full_name
        if lead_phone_provided:
            update_data["lead_phone"] = lead_phone

        response = (
            await self.db.table(TABLE)
            .update(update_data)
            .eq("id", appointment_id)
            .is_("deleted_at", "null")
            .execute()
        )
        if not response.data:
            return None
        return Appointment.from_row(as_row(response.data[0]))

    async def soft_delete(self, appointment_id: str) -> bool:
        response = (
            await self.db.table(TABLE)
            .update({"deleted_at": datetime.now(UTC).isoformat()})
            .eq("id", appointment_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return len(response.data) > 0


class AppointmentHistoryRepository:
    def __init__(self, db: AsyncClient) -> None:
        self.db = db

    async def get_by_appointment_id(
        self, appointment_id: str, *, page: int, page_size: int
    ) -> tuple[list[AppointmentHistoryEntry], int]:
        response = (
            await self.db.table(HISTORY_TABLE)
            .select("*", count=CountMethod.exact)
            .eq("appointment_id", appointment_id)
            .order("changed_at", desc=True)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execute()
        )
        entries = [AppointmentHistoryEntry.from_row(as_row(row)) for row in response.data]
        return entries, response.count or 0
