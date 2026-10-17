from datetime import UTC, datetime
from typing import Any

from postgrest.exceptions import APIError
from postgrest.types import CountMethod
from supabase import AsyncClient

from app.companies.exceptions import (
    CompanyAlreadyExistsError,
    CompanyUnitAlreadyExistsError,
    CompanyUserLinkAlreadyExistsError,
)
from app.companies.model import Company, CompanyUnit, CompanyUserLink
from app.shared.utils.postgrest import as_row

COMPANIES_TABLE = "companies"
COMPANY_UNITS_TABLE = "company_units"
COMPANY_USERS_TABLE = "company_users"
UNIQUE_VIOLATION = "23505"


class CompanyRepository:
    def __init__(self, db: AsyncClient) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> Company:
        try:
            response = await self.db.table(COMPANIES_TABLE).insert(data).execute()
        except APIError as exc:
            if exc.code == UNIQUE_VIOLATION:
                raise CompanyAlreadyExistsError(data["cnpj"]) from exc
            raise
        return Company.from_row(as_row(response.data[0]))

    async def get_all(
        self, *, page: int, page_size: int, company_ids: list[str] | None = None
    ) -> tuple[list[Company], int]:
        query = (
            self.db.table(COMPANIES_TABLE)
            .select("*", count=CountMethod.exact)
            .is_("deleted_at", "null")
        )
        if company_ids is not None:
            query = query.in_("id", company_ids)

        response = await (
            query.order("created_at", desc=True)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execute()
        )
        companies = [Company.from_row(as_row(row)) for row in response.data]
        return companies, response.count or 0

    async def get_by_id(self, company_id: str) -> Company | None:
        response = (
            await self.db.table(COMPANIES_TABLE)
            .select("*")
            .eq("id", company_id)
            .is_("deleted_at", "null")
            .maybe_single()
            .execute()
        )
        return Company.from_row(as_row(response.data)) if response else None

    async def update(self, company_id: str, data: dict[str, Any]) -> Company | None:
        try:
            response = (
                await self.db.table(COMPANIES_TABLE)
                .update(data)
                .eq("id", company_id)
                .is_("deleted_at", "null")
                .execute()
            )
        except APIError as exc:
            if exc.code == UNIQUE_VIOLATION:
                raise CompanyAlreadyExistsError(data.get("cnpj", "")) from exc
            raise
        return Company.from_row(as_row(response.data[0])) if response.data else None

    async def soft_delete(self, company_id: str) -> bool:
        response = (
            await self.db.table(COMPANIES_TABLE)
            .update({"deleted_at": datetime.now(UTC).isoformat()})
            .eq("id", company_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return len(response.data) > 0


class CompanyUnitRepository:
    def __init__(self, db: AsyncClient) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> CompanyUnit:
        try:
            response = await self.db.table(COMPANY_UNITS_TABLE).insert(data).execute()
        except APIError as exc:
            if exc.code == UNIQUE_VIOLATION:
                raise CompanyUnitAlreadyExistsError(
                    "Unit code or CNPJ already exists for this company"
                ) from exc
            raise
        return CompanyUnit.from_row(as_row(response.data[0]))

    async def get_all(
        self, company_id: str, *, page: int, page_size: int
    ) -> tuple[list[CompanyUnit], int]:
        response = (
            await self.db.table(COMPANY_UNITS_TABLE)
            .select("*", count=CountMethod.exact)
            .eq("company_id", company_id)
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execute()
        )
        units = [CompanyUnit.from_row(as_row(row)) for row in response.data]
        return units, response.count or 0

    async def get_by_id(self, unit_id: str) -> CompanyUnit | None:
        response = (
            await self.db.table(COMPANY_UNITS_TABLE)
            .select("*")
            .eq("id", unit_id)
            .is_("deleted_at", "null")
            .maybe_single()
            .execute()
        )
        return CompanyUnit.from_row(as_row(response.data)) if response else None

    async def update(self, unit_id: str, data: dict[str, Any]) -> CompanyUnit | None:
        try:
            response = (
                await self.db.table(COMPANY_UNITS_TABLE)
                .update(data)
                .eq("id", unit_id)
                .is_("deleted_at", "null")
                .execute()
            )
        except APIError as exc:
            if exc.code == UNIQUE_VIOLATION:
                raise CompanyUnitAlreadyExistsError(
                    "Unit code or CNPJ already exists for this company"
                ) from exc
            raise
        return CompanyUnit.from_row(as_row(response.data[0])) if response.data else None

    async def soft_delete(self, unit_id: str) -> bool:
        response = (
            await self.db.table(COMPANY_UNITS_TABLE)
            .update({"deleted_at": datetime.now(UTC).isoformat()})
            .eq("id", unit_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return len(response.data) > 0


class CompanyUserRepository:
    def __init__(self, db: AsyncClient) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> CompanyUserLink:
        try:
            response = await self.db.table(COMPANY_USERS_TABLE).insert(data).execute()
        except APIError as exc:
            if exc.code == UNIQUE_VIOLATION:
                raise CompanyUserLinkAlreadyExistsError from exc
            raise
        return CompanyUserLink.from_row(as_row(response.data[0]))

    async def get_all_for_company(
        self, company_id: str, *, page: int, page_size: int
    ) -> tuple[list[CompanyUserLink], int]:
        response = (
            await self.db.table(COMPANY_USERS_TABLE)
            .select("*", count=CountMethod.exact)
            .eq("company_id", company_id)
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execute()
        )
        links = [CompanyUserLink.from_row(as_row(row)) for row in response.data]
        return links, response.count or 0

    async def get_all_for_user(self, user_id: str) -> list[CompanyUserLink]:
        response = (
            await self.db.table(COMPANY_USERS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return [CompanyUserLink.from_row(as_row(row)) for row in response.data]

    async def get_by_id(self, link_id: str) -> CompanyUserLink | None:
        response = (
            await self.db.table(COMPANY_USERS_TABLE)
            .select("*")
            .eq("id", link_id)
            .is_("deleted_at", "null")
            .maybe_single()
            .execute()
        )
        return CompanyUserLink.from_row(as_row(response.data)) if response else None

    async def soft_delete(self, link_id: str) -> bool:
        response = (
            await self.db.table(COMPANY_USERS_TABLE)
            .update({"deleted_at": datetime.now(UTC).isoformat()})
            .eq("id", link_id)
            .is_("deleted_at", "null")
            .execute()
        )
        return len(response.data) > 0
