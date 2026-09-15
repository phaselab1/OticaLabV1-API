from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


@dataclass(frozen=True, slots=True)
class Appointment:
    id: str
    customer_id: str
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
            customer_id=row["customer_id"],
            scheduled_at=datetime.fromisoformat(row["scheduled_at"]),
            status=AppointmentStatus(row["status"]),
            notes=row.get("notes"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row.get("deleted_at") else None,
        )
