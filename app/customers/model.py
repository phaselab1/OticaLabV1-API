from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Customer:
    id: str
    company_id: str
    company_unit_id: str
    full_name: str
    date_of_birth: date
    phone: str | None
    created_by_user_id: str
    updated_by_user_id: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Customer":
        return cls(
            id=row["id"],
            company_id=row["company_id"],
            company_unit_id=row["company_unit_id"],
            full_name=row["full_name"],
            date_of_birth=date.fromisoformat(row["date_of_birth"]),
            phone=row.get("phone"),
            created_by_user_id=row["created_by_user_id"],
            updated_by_user_id=row.get("updated_by_user_id"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row.get("deleted_at") else None,
        )
