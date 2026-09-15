from typing import Annotated

from fastapi import Depends

from app.companies.repository import CompanyRepository, CompanyUnitRepository, CompanyUserRepository
from app.companies.service import CompanyService, CompanyUnitService, CompanyUserService
from app.core.dependencies import SupabaseClient


def get_company_repository(db: SupabaseClient) -> CompanyRepository:
    return CompanyRepository(db)


def get_company_unit_repository(db: SupabaseClient) -> CompanyUnitRepository:
    return CompanyUnitRepository(db)


def get_company_user_repository(db: SupabaseClient) -> CompanyUserRepository:
    return CompanyUserRepository(db)


def get_company_service(
    repository: Annotated[CompanyRepository, Depends(get_company_repository)],
    company_user_repository: Annotated[CompanyUserRepository, Depends(get_company_user_repository)],
) -> CompanyService:
    return CompanyService(repository, company_user_repository)


CompanyServiceDep = Annotated[CompanyService, Depends(get_company_service)]


def get_company_unit_service(
    repository: Annotated[CompanyUnitRepository, Depends(get_company_unit_repository)],
    company_repository: Annotated[CompanyRepository, Depends(get_company_repository)],
) -> CompanyUnitService:
    return CompanyUnitService(repository, company_repository)


CompanyUnitServiceDep = Annotated[CompanyUnitService, Depends(get_company_unit_service)]


def get_company_user_service(
    repository: Annotated[CompanyUserRepository, Depends(get_company_user_repository)],
    company_repository: Annotated[CompanyRepository, Depends(get_company_repository)],
    unit_repository: Annotated[CompanyUnitRepository, Depends(get_company_unit_repository)],
) -> CompanyUserService:
    return CompanyUserService(repository, company_repository, unit_repository)


CompanyUserServiceDep = Annotated[CompanyUserService, Depends(get_company_user_service)]
