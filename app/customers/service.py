from app.customers.exceptions import CustomerNotFoundError
from app.customers.model import Customer
from app.customers.repository import CustomerRepository
from app.customers.schema import CustomerCreate, CustomerUpdate
from app.shared.pagination import Page


class CustomerService:
    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    async def create(self, data: CustomerCreate) -> Customer:
        payload = data.model_dump(mode="json")
        return await self.repository.create(payload)

    async def get_all(self, *, page: int, page_size: int) -> Page[Customer]:
        customers, total = await self.repository.get_all(page=page, page_size=page_size)
        return Page(items=customers, page=page, page_size=page_size, total=total)

    async def get_by_id(self, customer_id: str) -> Customer:
        customer = await self.repository.get_by_id(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    async def update(self, customer_id: str, data: CustomerUpdate) -> Customer:
        payload = data.model_dump(mode="json", exclude_unset=True)
        customer = await self.repository.update(customer_id, payload)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    async def delete(self, customer_id: str) -> None:
        deleted = await self.repository.soft_delete(customer_id)
        if not deleted:
            raise CustomerNotFoundError(customer_id)
