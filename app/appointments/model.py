from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    ATTENDED = "attended"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


@dataclass(frozen=True, slots=True)
class Appointment:
    id: str
    company_id: str
    company_unit_id: str
    # Quem marcou o horário, antes de virar cliente. Preenchido sempre, mesmo
    # depois de customer_id ser setado (histórico do que foi informado na hora).
    lead_full_name: str
    lead_phone: str | None
    # Nulo até o agendamento ser marcado como `attended` (compareceu) — só
    # nesse momento o lead vira de fato um registro em `customers`.
    customer_id: str | None
    created_by_user_id: str
    updated_by_user_id: str | None
    scheduled_at: datetime
    status: AppointmentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Appointment":
        return cls(
            id=row["id"],
            company_id=row["company_id"],
            company_unit_id=row["company_unit_id"],
            lead_full_name=row["lead_full_name"],
            lead_phone=row.get("lead_phone"),
            customer_id=row.get("customer_id"),
            created_by_user_id=row["created_by_user_id"],
            updated_by_user_id=row.get("updated_by_user_id"),
            scheduled_at=datetime.fromisoformat(row["scheduled_at"]),
            status=AppointmentStatus(row["status"]),
            notes=row.get("notes"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row.get("deleted_at") else None,
        )


@dataclass(frozen=True, slots=True)
class AppointmentHistoryEntry:
    id: str
    appointment_id: str
    changed_by_user_id: str
    previous_scheduled_at: datetime | None
    new_scheduled_at: datetime | None
    previous_status: AppointmentStatus | None
    new_status: AppointmentStatus | None
    previous_notes: str | None
    new_notes: str | None
    changed_at: datetime

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "AppointmentHistoryEntry":
        return cls(
            id=row["id"],
            appointment_id=row["appointment_id"],
            changed_by_user_id=row["changed_by_user_id"],
            previous_scheduled_at=_optional_datetime(row.get("previous_scheduled_at")),
            new_scheduled_at=_optional_datetime(row.get("new_scheduled_at")),
            previous_status=_optional_status(row.get("previous_status")),
            new_status=_optional_status(row.get("new_status")),
            previous_notes=row.get("previous_notes"),
            new_notes=row.get("new_notes"),
            changed_at=datetime.fromisoformat(row["changed_at"]),
        )


def _optional_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _optional_status(value: str | None) -> AppointmentStatus | None:
    return AppointmentStatus(value) if value else None
