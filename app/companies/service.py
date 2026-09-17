from app.companies.exceptions import (
    CompanyNotFoundError,
    CompanyOrUnitRequiredError,
    CompanyUnitNotFoundError,
    CompanyUserLinkNotFoundError,
    ManagerRequiresUnitError,
)
from app.companies.model import Company, CompanyUnit, CompanyUserLink
from app.companies.repository import CompanyRepository, CompanyUnitRepository, CompanyUserRepository
from app.companies.schema import (
    CompanyCreate,
    CompanyUnitCreate,
    CompanyUnitUpdate,
    CompanyUpdate,
    CompanyUserGrant,
)
from app.core.exceptions import ForbiddenError
from app.shared.pagination import Page
from app.users.exceptions import UserNotFoundError
from app.users.model import User, UserRole
from app.users.repository import UserRepository


class CompanyService:
    def __init__(
        self, repository: CompanyRepository, company_user_service: "CompanyUserService"
    ) -> None:
        self.repository = repository
        self.company_user_service = company_user_service

    async def create(self, data: CompanyCreate, current_user: User) -> Company:
        payload = data.model_dump(mode="json")
        payload["created_by_user_id"] = current_user.id
        return await self.repository.create(payload)

    async def get_all(self, current_user: User, *, page: int, page_size: int) -> Page[Company]:
        company_ids: list[str] | None = None
        if current_user.role != UserRole.SUPER_ADMIN:
            links = await self.company_user_service.repository.get_all_for_user(current_user.id)
            company_ids = list({link.company_id for link in links})
            if not company_ids:
                return Page(items=[], page=page, page_size=page_size, total=0)

        companies, total = await self.repository.get_all(
            page=page, page_size=page_size, company_ids=company_ids
        )
        return Page(items=companies, page=page, page_size=page_size, total=total)

    async def get_by_id(self, company_id: str, current_user: User) -> Company:
        company = await self.repository.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError(company_id)

        if not await self.company_user_service.has_company_access(current_user, company_id):
            raise CompanyNotFoundError(company_id)

        return company

    async def update(self, company_id: str, data: CompanyUpdate, current_user: User) -> Company:
        if not await self.company_user_service.has_company_admin_access(current_user, company_id):
            raise ForbiddenError("Insufficient access to manage this company")

        payload = data.model_dump(mode="json", exclude_unset=True)
        company = await self.repository.update(company_id, payload)
        if company is None:
            raise CompanyNotFoundError(company_id)
        return company

    async def delete(self, company_id: str) -> None:
        deleted = await self.repository.soft_delete(company_id)
        if not deleted:
            raise CompanyNotFoundError(company_id)


class CompanyUnitService:
    def __init__(
        self,
        repository: CompanyUnitRepository,
        company_repository: CompanyRepository,
        company_user_service: "CompanyUserService",
    ) -> None:
        self.repository = repository
        self.company_repository = company_repository
        self.company_user_service = company_user_service

    async def create(
        self, company_id: str, data: CompanyUnitCreate, current_user: User
    ) -> CompanyUnit:
        company = await self.company_repository.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError(company_id)

        payload = data.model_dump(mode="json")
        payload["company_id"] = company_id
        payload["created_by_user_id"] = current_user.id
        return await self.repository.create(payload)

    async def get_all(
        self, company_id: str, current_user: User, *, page: int, page_size: int
    ) -> Page[CompanyUnit]:
        if not await self.company_user_service.has_company_access(current_user, company_id):
            raise CompanyNotFoundError(company_id)

        units, total = await self.repository.get_all(company_id, page=page, page_size=page_size)
        return Page(items=units, page=page, page_size=page_size, total=total)

    async def get_by_id(self, unit_id: str, current_user: User) -> CompanyUnit:
        unit = await self.repository.get_by_id(unit_id)
        if unit is None:
            raise CompanyUnitNotFoundError(unit_id)

        if not await self.company_user_service.has_unit_access(
            current_user, unit.company_id, unit.id
        ):
            raise CompanyUnitNotFoundError(unit_id)

        return unit

    async def update(
        self, unit_id: str, data: CompanyUnitUpdate, current_user: User
    ) -> CompanyUnit:
        existing = await self.get_by_id(unit_id, current_user)

        payload = data.model_dump(mode="json", exclude_unset=True)
        unit = await self.repository.update(existing.id, payload)
        if unit is None:
            raise CompanyUnitNotFoundError(unit_id)
        return unit

    async def delete(self, unit_id: str) -> None:
        deleted = await self.repository.soft_delete(unit_id)
        if not deleted:
            raise CompanyUnitNotFoundError(unit_id)


class CompanyUserService:
    def __init__(
        self,
        repository: CompanyUserRepository,
        company_repository: CompanyRepository,
        unit_repository: CompanyUnitRepository,
        user_repository: UserRepository,
    ) -> None:
        self.repository = repository
        self.company_repository = company_repository
        self.unit_repository = unit_repository
        self.user_repository = user_repository

    async def grant(
        self, company_id: str, data: CompanyUserGrant, current_user: User
    ) -> CompanyUserLink:
        if not await self.has_company_admin_access(current_user, company_id):
            raise ForbiddenError("Insufficient access to manage this company")

        company = await self.company_repository.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError(company_id)

        target_user = await self.user_repository.get_by_id(data.user_id)
        if target_user is None:
            raise UserNotFoundError(data.user_id)

        if target_user.role == UserRole.MANAGER and data.unit_id is None:
            raise ManagerRequiresUnitError(data.user_id)

        if data.unit_id is not None:
            unit = await self.unit_repository.get_by_id(data.unit_id)
            if unit is None or unit.company_id != company_id:
                raise CompanyUnitNotFoundError(data.unit_id)

        payload = {
            "company_id": company_id,
            "user_id": data.user_id,
            "unit_id": data.unit_id,
            "granted_by_user_id": current_user.id,
        }
        return await self.repository.create(payload)

    async def get_all_for_company(
        self, company_id: str, current_user: User, *, page: int, page_size: int
    ) -> Page[CompanyUserLink]:
        if not await self.has_company_admin_access(current_user, company_id):
            raise ForbiddenError("Insufficient access to manage this company")

        links, total = await self.repository.get_all_for_company(
            company_id, page=page, page_size=page_size
        )
        return Page(items=links, page=page, page_size=page_size, total=total)

    async def revoke(self, link_id: str, current_user: User) -> None:
        link = await self.repository.get_by_id(link_id)
        if link is None:
            raise CompanyUserLinkNotFoundError(link_id)

        if not await self.has_company_admin_access(current_user, link.company_id):
            raise ForbiddenError("Insufficient access to manage this company")

        await self.repository.soft_delete(link_id)

    async def has_company_admin_access(self, user: User, company_id: str) -> bool:
        if user.role == UserRole.SUPER_ADMIN:
            return True
        links = await self.repository.get_all_for_user(user.id)
        return any(link.company_id == company_id and link.unit_id is None for link in links)

    async def has_company_access(self, user: User, company_id: str) -> bool:
        if user.role == UserRole.SUPER_ADMIN:
            return True
        links = await self.repository.get_all_for_user(user.id)
        return any(link.company_id == company_id for link in links)

    async def has_unit_access(self, user: User, company_id: str, unit_id: str) -> bool:
        if user.role == UserRole.SUPER_ADMIN:
            return True
        links = await self.repository.get_all_for_user(user.id)
        return any(
            link.company_id == company_id and (link.unit_id is None or link.unit_id == unit_id)
            for link in links
        )

    async def resolve_company_and_unit(
        self, current_user: User, company_id: str | None, unit_id: str | None
    ) -> tuple[str, str]:
        if current_user.role == UserRole.SUPER_ADMIN:
            if company_id is None or unit_id is None:
                raise CompanyOrUnitRequiredError(
                    "super_admin must provide both company_id and company_unit_id"
                )
            return company_id, unit_id

        links = await self.repository.get_all_for_user(current_user.id)

        if company_id is None:
            company_ids = {link.company_id for link in links}
            if len(company_ids) != 1:
                raise CompanyOrUnitRequiredError(
                    "company_id is required (user has access to zero or multiple companies)"
                )
            company_id = next(iter(company_ids))
        elif not any(link.company_id == company_id for link in links):
            raise ForbiddenError(f"No access to company {company_id}")

        if unit_id is None:
            company_links = [link for link in links if link.company_id == company_id]
            has_whole_company_access = any(link.unit_id is None for link in company_links)
            if has_whole_company_access:
                raise CompanyOrUnitRequiredError(
                    "company_unit_id is required (user has whole-company access)"
                )

            unit_ids = {link.unit_id for link in company_links if link.unit_id is not None}
            if len(unit_ids) != 1:
                raise CompanyOrUnitRequiredError(
                    "company_unit_id is required (user has access to zero or multiple units)"
                )
            unit_id = next(iter(unit_ids))
        elif not await self.has_unit_access(current_user, company_id, unit_id):
            raise ForbiddenError(f"No access to unit {unit_id} of company {company_id}")

        return company_id, unit_id
