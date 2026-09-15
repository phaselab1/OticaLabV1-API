from typing import Annotated

from fastapi import Depends

from app.core.dependencies import SupabaseClient
from app.customers.repository import CustomerRepository
from app.customers.service import CustomerService


def get_customer_repository(db: SupabaseClient) -> CustomerRepository:
    return CustomerRepository(db)


def get_customer_service(
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> CustomerService:
    return CustomerService(repository)


CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]
