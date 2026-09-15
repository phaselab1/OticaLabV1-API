from app.companies.service import CompanyUserService
from app.core.exceptions import ForbiddenError
from app.customers.exceptions import CustomerNotFoundError
from app.customers.model import Customer
from app.customers.repository import CustomerRepository
from app.customers.schema import CustomerCreate, CustomerUpdate
from app.shared.pagination import Page
from app.users.model import User


class CustomerService:
    def __init__(
        self, repository: CustomerRepository, company_user_service: CompanyUserService
    ) -> None:
        self.repository = repository
        self.company_user_service = company_user_service

    async def create(self, data: CustomerCreate, current_user: User) -> Customer:
        company_id, company_unit_id = await self.company_user_service.resolve_company_and_unit(
            current_user, data.company_id, data.company_unit_id
        )

        payload = data.model_dump(mode="json", exclude={"company_id", "company_unit_id"})
        payload["company_id"] = company_id
        payload["company_unit_id"] = company_unit_id
        payload["created_by_user_id"] = current_user.id
        return await self.repository.create(payload)

    async def get_all(
        self,
        *,
        page: int,
        page_size: int,
        company_id: str | None = None,
        company_unit_id: str | None = None,
    ) -> Page[Customer]:
        customers, total = await self.repository.get_all(
            page=page, page_size=page_size, company_id=company_id, company_unit_id=company_unit_id
        )
        return Page(items=customers, page=page, page_size=page_size, total=total)

    async def get_by_id(self, customer_id: str) -> Customer:
        customer = await self.repository.get_by_id(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    async def update(self, customer_id: str, data: CustomerUpdate, current_user: User) -> Customer:
        existing = await self.get_by_id(customer_id)

        if not await self.company_user_service.has_unit_access(
            current_user, existing.company_id, existing.company_unit_id
        ):
            raise ForbiddenError(
                f"No access to unit {existing.company_unit_id} of company {existing.company_id}"
            )

        payload = data.model_dump(mode="json", exclude_unset=True)
        payload["updated_by_user_id"] = current_user.id
        customer = await self.repository.update(customer_id, payload)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    async def delete(self, customer_id: str) -> None:
        deleted = await self.repository.soft_delete(customer_id)
        if not deleted:
            raise CustomerNotFoundError(customer_id)
