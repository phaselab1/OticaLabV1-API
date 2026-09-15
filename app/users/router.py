from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.shared.pagination import Page
from app.users.dependencies import CurrentUser, UserServiceDep, require_role
from app.users.model import User, UserRole
from app.users.schema import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

RequireSuperAdmin = Annotated[User, Depends(require_role(UserRole.SUPER_ADMIN))]


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar usuário",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer role `super_admin`."},
        409: {"description": "Já existe um usuário ativo com esse e-mail."},
        422: {"description": "Dados inválidos (ex: senha com menos de 8 caracteres)."},
    },
)
async def create_user(
    data: UserCreate, service: UserServiceDep, _current_user: RequireSuperAdmin
) -> User:
    """
    Cria um novo usuário do sistema. **Exige role `super_admin`.**

    A senha é hasheada com bcrypt antes de ser persistida — nunca é
    armazenada nem retornada em texto plano. O usuário criado ainda não
    tem acesso a nenhuma empresa/unidade; isso é concedido separadamente
    via `POST /companies/{company_id}/users`.
    """
    return await service.create(data)


@router.get(
    "/",
    response_model=Page[UserResponse],
    summary="Listar usuários",
    responses={401: {"description": "Token ausente ou inválido."}},
)
async def list_users(
    service: UserServiceDep,
    _current_user: CurrentUser,
    page: Annotated[int, Query(ge=1, description="Número da página, começando em 1.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Itens por página (máx. 100).")] = 20,
) -> Page[User]:
    """Lista todos os usuários ativos (soft-deletados não aparecem), paginado."""
    return await service.get_all(page=page, page_size=page_size)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Buscar usuário por ID",
    responses={
        401: {"description": "Token ausente ou inválido."},
        404: {"description": "Usuário não encontrado (ou soft-deletado)."},
    },
)
async def get_user(user_id: str, service: UserServiceDep, _current_user: CurrentUser) -> User:
    """Busca um usuário pelo UUID."""
    return await service.get_by_id(user_id)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Atualizar usuário",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer role `super_admin`."},
        404: {"description": "Usuário não encontrado (ou soft-deletado)."},
        409: {"description": "Já existe um usuário ativo com o novo e-mail informado."},
    },
)
async def update_user(
    user_id: str, data: UserUpdate, service: UserServiceDep, _current_user: RequireSuperAdmin
) -> User:
    """
    Atualiza campos de um usuário. **Exige role `super_admin`.**

    Todos os campos são opcionais — só os enviados são alterados
    (atualização parcial). A senha não pode ser alterada por esta rota.
    """
    return await service.update(user_id, data)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir usuário",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Requer role `super_admin`."},
        404: {"description": "Usuário não encontrado (ou já soft-deletado)."},
    },
)
async def delete_user(
    user_id: str, service: UserServiceDep, _current_user: RequireSuperAdmin
) -> None:
    """
    Remove um usuário (soft delete). **Exige role `super_admin`.**

    O usuário some das listagens e não consegue mais fazer login, mas a
    linha permanece no banco (`deleted_at` preenchido) — necessário para
    manter a integridade referencial do histórico de auditoria.
    """
    await service.delete(user_id)
