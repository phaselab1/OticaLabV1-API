from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Company:
    id: str
    name: str
    cnpj: str
    state: str
    city: str
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Company":
        return cls(
            id=row["id"],
            name=row["name"],
            cnpj=row["cnpj"],
            state=row["state"],
            city=row["city"],
            created_by_user_id=row["created_by_user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row.get("deleted_at") else None,
        )


@dataclass(frozen=True, slots=True)
class CompanyUnit:
    id: str
    company_id: str
    name: str
    code: str
    cnpj: str
    state: str
    city: str
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "CompanyUnit":
        return cls(
            id=row["id"],
            company_id=row["company_id"],
            name=row["name"],
            code=row["code"],
            cnpj=row["cnpj"],
            state=row["state"],
            city=row["city"],
            created_by_user_id=row["created_by_user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row.get("deleted_at") else None,
        )


@dataclass(frozen=True, slots=True)
class CompanyUserLink:
    id: str
    company_id: str
    user_id: str
    unit_id: str | None
    granted_by_user_id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "CompanyUserLink":
        return cls(
            id=row["id"],
            company_id=row["company_id"],
            user_id=row["user_id"],
            unit_id=row.get("unit_id"),
            granted_by_user_id=row["granted_by_user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row.get("deleted_at") else None,
        )
