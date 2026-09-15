from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class UserRole(StrEnum):
    MASTER = "master"
    ATTENDANT = "attendant"


@dataclass(frozen=True, slots=True)
class User:
    id: str
    full_name: str
    email: str
    password_hash: str
    role: UserRole
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "User":
        return cls(
            id=row["id"],
            full_name=row["full_name"],
            email=row["email"],
            password_hash=row["password_hash"],
            role=UserRole(row["role"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row.get("deleted_at") else None,
        )
