from typing import Annotated

from fastapi import Depends

from app.companies.dependencies import get_company_user_service
from app.companies.service import CompanyUserService
from app.core.dependencies import SupabaseClient
from app.customers.repository import CustomerRepository
from app.customers.service import CustomerService


def get_customer_repository(db: SupabaseClient) -> CustomerRepository:
    return CustomerRepository(db)


def get_customer_service(
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    company_user_service: Annotated[CompanyUserService, Depends(get_company_user_service)],
) -> CustomerService:
    return CustomerService(repository, company_user_service)


CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]
