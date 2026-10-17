from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

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

CompanyIdPath = Annotated[str, Path(description="UUID da empresa.")]


@router.post(
    "/",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar empresa",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer role `super_admin`."},
        409: {"description": "Já existe uma empresa ativa com esse CNPJ."},
        422: {"description": "Dados inválidos (ex: CNPJ fora do formato, UF inexistente)."},
    },
)
async def create_company(
    data: CompanyCreate, service: CompanyServiceDep, current_user: RequireSuperAdmin
) -> Company:
    """Cria uma nova empresa. **Exige role `super_admin`.**"""
    return await service.create(data, current_user)


@router.get(
    "/",
    response_model=Page[CompanyResponse],
    summary="Listar empresas",
    responses={401: {"description": "Token ausente ou inválido."}},
)
async def list_companies(
    service: CompanyServiceDep,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1, description="Número da página, começando em 1.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Itens por página (máx. 100).")] = 20,
) -> Page[Company]:
    """
    Lista empresas ativas, paginado.

    `super_admin` vê todas as empresas. Qualquer outro role vê **só** as
    empresas às quais tem algum vínculo de acesso em `company_users`.
    """
    return await service.get_all(current_user, page=page, page_size=page_size)


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Buscar empresa por ID",
    responses={
        401: {"description": "Token ausente ou inválido."},
        404: {"description": "Empresa não encontrada, soft-deletada, ou sem acesso."},
    },
)
async def get_company(
    company_id: CompanyIdPath, service: CompanyServiceDep, current_user: CurrentUser
) -> Company:
    """Busca uma empresa pelo UUID. Requer algum vínculo de acesso a ela (ou `super_admin`)."""
    return await service.get_by_id(company_id, current_user)


@router.put(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Atualizar empresa",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer permissão de administrador na empresa."},
        404: {"description": "Empresa não encontrada (ou soft-deletada)."},
        409: {"description": "Já existe outra empresa ativa com o novo CNPJ informado."},
    },
)
async def update_company(
    company_id: CompanyIdPath,
    data: CompanyUpdate,
    service: CompanyServiceDep,
    current_user: CurrentUser,
) -> Company:
    """Atualiza campos de uma empresa (parcial). Requer acesso de admin/super_admin."""
    return await service.update(company_id, data, current_user)


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir empresa",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer role `super_admin`."},
        404: {"description": "Empresa não encontrada (ou já soft-deletada)."},
    },
)
async def delete_company(
    company_id: CompanyIdPath, service: CompanyServiceDep, _current_user: RequireSuperAdmin
) -> None:
    """
    Remove uma empresa (soft delete). **Exige role `super_admin`.**

    Não remove em cascata unidades/clientes/agendamentos já existentes —
    eles continuam no banco, mas o trigger `enforce_*_parent_active`
    impede qualquer criação nova sob uma empresa desativada.
    """
    await service.delete(company_id)


@router.post(
    "/{company_id}/units",
    response_model=CompanyUnitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar unidade",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer role `super_admin`."},
        404: {"description": "Empresa não encontrada (ou soft-deletada)."},
        409: {"description": "Já existe uma unidade ativa com esse `code` ou CNPJ nesta empresa."},
        422: {"description": "Dados inválidos."},
    },
)
async def create_company_unit(
    company_id: CompanyIdPath,
    data: CompanyUnitCreate,
    service: CompanyUnitServiceDep,
    current_user: RequireSuperAdmin,
) -> CompanyUnit:
    """Cria uma nova unidade (filial) dentro de uma empresa. **Exige role `super_admin`.**"""
    return await service.create(company_id, data, current_user)


@router.get(
    "/{company_id}/units",
    response_model=Page[CompanyUnitResponse],
    summary="Listar unidades de uma empresa",
    responses={
        401: {"description": "Token ausente ou inválido."},
        404: {"description": "Empresa não encontrada, soft-deletada, ou sem acesso."},
    },
)
async def list_company_units(
    company_id: CompanyIdPath,
    service: CompanyUnitServiceDep,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[CompanyUnit]:
    """Lista as unidades ativas de uma empresa, paginado. Requer algum vínculo de acesso a ela."""
    return await service.get_all(company_id, current_user, page=page, page_size=page_size)


@router.get(
    "/{company_id}/units/{unit_id}",
    response_model=CompanyUnitResponse,
    summary="Buscar unidade por ID",
    responses={
        401: {"description": "Token ausente ou inválido."},
        404: {"description": "Unidade não encontrada, soft-deletada, ou sem acesso."},
    },
)
async def get_company_unit(
    unit_id: Annotated[str, Path(description="UUID da unidade.")],
    service: CompanyUnitServiceDep,
    current_user: CurrentUser,
) -> CompanyUnit:
    """Busca uma unidade pelo UUID. Requer acesso à unidade (ou à empresa inteira)."""
    return await service.get_by_id(unit_id, current_user)


@router.put(
    "/{company_id}/units/{unit_id}",
    response_model=CompanyUnitResponse,
    summary="Atualizar unidade",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer permissão de administrador na unidade/empresa."},
        404: {"description": "Unidade não encontrada (ou soft-deletada)."},
        409: {
            "description": "Já existe outra unidade ativa com o novo `code` ou CNPJ nesta empresa."
        },
    },
)
async def update_company_unit(
    unit_id: Annotated[str, Path(description="UUID da unidade.")],
    data: CompanyUnitUpdate,
    service: CompanyUnitServiceDep,
    current_user: CurrentUser,
) -> CompanyUnit:
    """Atualiza campos de uma unidade (parcial). Requer permissão de admin/super_admin."""
    return await service.update(unit_id, data, current_user)


@router.delete(
    "/{company_id}/units/{unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir unidade",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer role `super_admin`."},
        404: {"description": "Unidade não encontrada (ou já soft-deletada)."},
    },
)
async def delete_company_unit(
    unit_id: Annotated[str, Path(description="UUID da unidade.")],
    service: CompanyUnitServiceDep,
    _current_user: RequireSuperAdmin,
) -> None:
    """Remove uma unidade (soft delete). **Exige role `super_admin`.**"""
    await service.delete(unit_id)


@router.post(
    "/{company_id}/users",
    response_model=CompanyUserLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Conceder acesso a um usuário",
    responses={
        401: {"description": "Token ausente ou inválido."},
        400: {
            "description": (
                "Usuário tem role `manager` mas `unit_id` não foi informado "
                "— manager precisa sempre de uma unidade específica."
            )
        },
        403: {
            "description": (
                "Requer acesso de administrador a esta empresa "
                "(`super_admin` ou `admin` vinculado à empresa inteira)."
            )
        },
        404: {"description": "Empresa, usuário ou unidade informada não encontrados."},
        409: {"description": "Usuário já tem um vínculo ativo idêntico (mesma empresa/unidade)."},
    },
)
async def grant_company_access(
    company_id: CompanyIdPath,
    data: CompanyUserGrant,
    service: CompanyUserServiceDep,
    current_user: CurrentUser,
) -> CompanyUserLink:
    """
    Concede a um usuário acesso a uma empresa (inteira, se `unit_id`
    omitido) ou a uma unidade específica.

    Quem pode conceder: `super_admin` (qualquer empresa) ou `admin` com
    vínculo de empresa inteira na empresa em questão.
    """
    return await service.grant(company_id, data, current_user)


@router.get(
    "/{company_id}/users",
    response_model=Page[CompanyUserLinkResponse],
    summary="Listar acessos concedidos numa empresa",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer acesso de administrador a esta empresa."},
    },
)
async def list_company_access(
    company_id: CompanyIdPath,
    service: CompanyUserServiceDep,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[CompanyUserLink]:
    """Lista os vínculos de acesso ativos concedidos nesta empresa, paginado."""
    return await service.get_all_for_company(
        company_id, current_user, page=page, page_size=page_size
    )


@router.delete(
    "/{company_id}/users/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revogar acesso de um usuário",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer acesso de administrador a esta empresa."},
        404: {"description": "Vínculo de acesso não encontrado (ou já revogado)."},
    },
)
async def revoke_company_access(
    link_id: Annotated[str, Path(description="UUID do vínculo de acesso (retornado ao conceder).")],
    service: CompanyUserServiceDep,
    current_user: CurrentUser,
) -> None:
    """
    Revoga um vínculo de acesso (soft delete do vínculo, não da empresa/
    unidade/usuário). Quem pode revogar: `super_admin` ou `admin` com
    vínculo de empresa inteira na empresa do vínculo.
    """
    await service.revoke(link_id, current_user)
