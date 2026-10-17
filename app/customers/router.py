from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.customers.dependencies import CustomerServiceDep
from app.customers.model import Customer
from app.customers.schema import CustomerCreate, CustomerResponse, CustomerUpdate
from app.shared.pagination import Page
from app.users.dependencies import CurrentUser, require_role
from app.users.model import User, UserRole

router = APIRouter(prefix="/customers", tags=["customers"])

# attendant não exclui cliente — só cadastra/consulta/atualiza. Excluir é
# reservado a quem gerencia a unidade/empresa (manager e acima).
RequireCustomerDeleteRole = Annotated[
    User, Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER))
]


@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar cliente",
    responses={
        400: {
            "description": (
                "`company_id`/`company_unit_id` não informados e não puderam ser "
                "deduzidos automaticamente a partir do papel/vínculos do usuário."
            )
        },
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Usuário não tem acesso à empresa/unidade informada."},
        404: {"description": "Empresa ou unidade informada não encontrada."},
        409: {"description": "Já existe um cliente ativo com esse nome nesta empresa."},
        422: {"description": "Dados inválidos (ex: telefone fora do formato)."},
    },
)
async def create_customer(
    data: CustomerCreate, service: CustomerServiceDep, current_user: CurrentUser
) -> Customer:
    """
    Cadastra um novo cliente.

    `company_id`/`company_unit_id` seguem a regra de auto-preenchimento
    por papel do usuário autenticado — veja a descrição da API em `/docs`.
    `created_by_user_id` vem sempre do usuário autenticado, nunca do corpo
    da requisição.
    """
    return await service.create(data, current_user)


@router.get(
    "/",
    response_model=Page[CustomerResponse],
    summary="Listar clientes",
    responses={401: {"description": "Token ausente ou inválido."}},
)
async def list_customers(
    service: CustomerServiceDep,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1, description="Número da página, começando em 1.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Itens por página (máx. 100).")] = 20,
    company_id: Annotated[str | None, Query(description="Filtra por UUID da empresa.")] = None,
    company_unit_id: Annotated[str | None, Query(description="Filtra por UUID da unidade.")] = None,
) -> Page[Customer]:
    """
    Lista clientes ativos, paginado.

    `super_admin` pode filtrar livremente por empresa/unidade (ou ver
    tudo, sem filtro). Qualquer outro role é restrito ao escopo do seu
    próprio vínculo de acesso — os filtros, se informados, precisam estar
    dentro desse escopo; se omitidos, são preenchidos automaticamente
    quando não houver ambiguidade (mesma regra de `POST /customers`).
    """
    return await service.get_all(
        current_user,
        page=page,
        page_size=page_size,
        company_id=company_id,
        company_unit_id=company_unit_id,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Buscar cliente por ID",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Usuário não tem acesso à unidade deste cliente."},
        404: {"description": "Cliente não encontrado (ou soft-deletado)."},
    },
)
async def get_customer(
    customer_id: Annotated[str, Path(description="UUID do cliente.")],
    service: CustomerServiceDep,
    current_user: CurrentUser,
) -> Customer:
    """Busca um cliente pelo UUID. Requer acesso à unidade/empresa do cliente."""
    return await service.get_by_id(customer_id, current_user)


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Atualizar cliente",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Usuário não tem acesso à unidade deste cliente."},
        404: {"description": "Cliente não encontrado (ou soft-deletado)."},
        409: {"description": "Novo nome já pertence a outro cliente ativo nesta empresa."},
    },
)
async def update_customer(
    customer_id: Annotated[str, Path(description="UUID do cliente.")],
    data: CustomerUpdate,
    service: CustomerServiceDep,
    current_user: CurrentUser,
) -> Customer:
    """
    Atualiza campos de um cliente (parcial). Empresa/unidade do cliente
    não podem ser alteradas por esta rota. `updated_by_user_id` vem do
    usuário autenticado.
    """
    return await service.update(customer_id, data, current_user)


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir cliente",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {
            "description": (
                "Requer role `super_admin`, `admin` ou `manager` (attendant não pode "
                "excluir cliente), ou usuário não tem acesso à unidade deste cliente."
            )
        },
        404: {"description": "Cliente não encontrado (ou já soft-deletado)."},
    },
)
async def delete_customer(
    customer_id: Annotated[str, Path(description="UUID do cliente.")],
    service: CustomerServiceDep,
    current_user: RequireCustomerDeleteRole,
) -> None:
    """Remove um cliente (soft delete). **Exige role `super_admin`, `admin` ou
    `manager`** — attendant não tem permissão para excluir clientes. Agendamentos
    existentes não são afetados."""
    await service.delete(customer_id, current_user)
