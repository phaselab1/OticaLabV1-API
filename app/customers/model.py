from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Customer:
    id: str
    full_name: str
    date_of_birth: date
    phone: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Customer":
        return cls(
            id=row["id"],
            full_name=row["full_name"],
            date_of_birth=date.fromisoformat(row["date_of_birth"]),
            phone=row.get("phone"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row.get("deleted_at") else None,
        )
