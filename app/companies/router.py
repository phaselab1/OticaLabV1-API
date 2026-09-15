from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.companies.dependencies import (
    CompanyServiceDep,
    CompanyUnitServiceDep,
    CompanyUserServiceDep,
)
from app.companies.model import Company, CompanyUnit, CompanyUserLink
from app.companies.schema import (
    CompanyCreate,
    CompanyResponse,
    CompanyUnitCreate,
    CompanyUnitResponse,
    CompanyUnitUpdate,
    CompanyUpdate,
    CompanyUserGrant,
    CompanyUserLinkResponse,
)
from app.shared.pagination import Page
from app.users.dependencies import CurrentUser, require_role
from app.users.model import User, UserRole

router = APIRouter(prefix="/companies", tags=["companies"])

RequireSuperAdmin = Annotated[User, Depends(require_role(UserRole.SUPER_ADMIN))]


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    data: CompanyCreate, service: CompanyServiceDep, current_user: RequireSuperAdmin
) -> Company:
    return await service.create(data, current_user)


@router.get("/", response_model=Page[CompanyResponse])
async def list_companies(
    service: CompanyServiceDep,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[Company]:
    return await service.get_all(current_user, page=page, page_size=page_size)


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: str, service: CompanyServiceDep) -> Company:
    return await service.get_by_id(company_id)


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    data: CompanyUpdate,
    service: CompanyServiceDep,
    _current_user: RequireSuperAdmin,
) -> Company:
    return await service.update(company_id, data)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: str, service: CompanyServiceDep, _current_user: RequireSuperAdmin
) -> None:
    await service.delete(company_id)


@router.post(
    "/{company_id}/units", response_model=CompanyUnitResponse, status_code=status.HTTP_201_CREATED
)
async def create_company_unit(
    company_id: str,
    data: CompanyUnitCreate,
    service: CompanyUnitServiceDep,
    current_user: RequireSuperAdmin,
) -> CompanyUnit:
    return await service.create(company_id, data, current_user)


@router.get("/{company_id}/units", response_model=Page[CompanyUnitResponse])
async def list_company_units(
    company_id: str,
    service: CompanyUnitServiceDep,
    _current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[CompanyUnit]:
    return await service.get_all(company_id, page=page, page_size=page_size)


@router.get("/{company_id}/units/{unit_id}", response_model=CompanyUnitResponse)
async def get_company_unit(unit_id: str, service: CompanyUnitServiceDep) -> CompanyUnit:
    return await service.get_by_id(unit_id)


@router.put("/{company_id}/units/{unit_id}", response_model=CompanyUnitResponse)
async def update_company_unit(
    unit_id: str,
    data: CompanyUnitUpdate,
    service: CompanyUnitServiceDep,
    _current_user: RequireSuperAdmin,
) -> CompanyUnit:
    return await service.update(unit_id, data)


@router.delete("/{company_id}/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_unit(
    unit_id: str, service: CompanyUnitServiceDep, _current_user: RequireSuperAdmin
) -> None:
    await service.delete(unit_id)


@router.post(
    "/{company_id}/users",
    response_model=CompanyUserLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_company_access(
    company_id: str,
    data: CompanyUserGrant,
    service: CompanyUserServiceDep,
    current_user: CurrentUser,
) -> CompanyUserLink:
    return await service.grant(company_id, data, current_user)


@router.get("/{company_id}/users", response_model=Page[CompanyUserLinkResponse])
async def list_company_access(
    company_id: str,
    service: CompanyUserServiceDep,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[CompanyUserLink]:
    return await service.get_all_for_company(
        company_id, current_user, page=page, page_size=page_size
    )


@router.delete("/{company_id}/users/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_company_access(
    link_id: str, service: CompanyUserServiceDep, current_user: CurrentUser
) -> None:
    await service.revoke(link_id, current_user)
