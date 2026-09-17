from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.appointments.dependencies import AppointmentHistoryServiceDep, AppointmentServiceDep
from app.appointments.model import Appointment, AppointmentHistoryEntry, AppointmentStatus
from app.appointments.schema import (
    AppointmentCreate,
    AppointmentHistoryResponse,
    AppointmentReschedule,
    AppointmentResponse,
    AppointmentUpdate,
)
from app.shared.pagination import Page
from app.users.dependencies import CurrentUser

router = APIRouter(prefix="/appointments", tags=["appointments"])

AppointmentIdPath = Annotated[str, Path(description="UUID do agendamento.")]


@router.post(
    "/",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar agendamento",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Usuário não tem acesso à unidade deste cliente."},
        404: {"description": "Cliente não encontrado (ou soft-deletado)."},
        409: {"description": "Este cliente já tem um agendamento ativo neste exato horário."},
        422: {"description": "Dados inválidos."},
    },
)
async def create_appointment(
    data: AppointmentCreate, service: AppointmentServiceDep, current_user: CurrentUser
) -> Appointment:
    """
    Cria um agendamento para um cliente. Empresa/unidade do agendamento
    são herdadas do cliente (não são informadas na requisição).
    `created_by_user_id` vem do usuário autenticado; status inicial é
    sempre `scheduled`.
    """
    return await service.create(data, current_user)


@router.get(
    "/",
    response_model=Page[AppointmentResponse],
    summary="Listar agendamentos",
    responses={401: {"description": "Token ausente ou inválido."}},
)
async def list_appointments(
    service: AppointmentServiceDep,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1, description="Número da página, começando em 1.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Itens por página (máx. 100).")] = 20,
    customer_id: Annotated[str | None, Query(description="Filtra por UUID do cliente.")] = None,
    status_filter: Annotated[
        AppointmentStatus | None, Query(alias="status", description="Filtra por status.")
    ] = None,
) -> Page[Appointment]:
    """
    Lista agendamentos ativos, ordenados por `scheduled_at` crescente,
    paginado. `super_admin` vê tudo; qualquer outro role é restrito ao
    escopo do seu próprio vínculo de acesso.
    """
    return await service.get_all(
        current_user,
        page=page,
        page_size=page_size,
        customer_id=customer_id,
        status=status_filter,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Buscar agendamento por ID",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Usuário não tem acesso à unidade deste agendamento."},
        404: {"description": "Agendamento não encontrado (ou soft-deletado)."},
    },
)
async def get_appointment(
    appointment_id: AppointmentIdPath, service: AppointmentServiceDep, current_user: CurrentUser
) -> Appointment:
    """Busca um agendamento pelo UUID."""
    return await service.get_by_id(appointment_id, current_user)


@router.get(
    "/{appointment_id}/history",
    response_model=Page[AppointmentHistoryResponse],
    summary="Histórico de alterações do agendamento",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Usuário não tem acesso à unidade deste agendamento."},
        404: {"description": "Agendamento não encontrado (ou soft-deletado)."},
    },
)
async def list_appointment_history(
    appointment_id: AppointmentIdPath,
    service: AppointmentHistoryServiceDep,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[AppointmentHistoryEntry]:
    """
    Lista, do mais recente para o mais antigo, todas as alterações já
    feitas neste agendamento. Somente leitura — a tabela de histórico é
    imutável (nem um superusuário do Postgres consegue alterá-la), cada
    linha é gravada automaticamente por `PUT /appointments/{id}`.
    """
    return await service.get_by_appointment(
        appointment_id, current_user, page=page, page_size=page_size
    )


@router.put(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Atualizar agendamento",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Usuário não tem acesso à unidade deste cliente."},
        404: {"description": "Agendamento não encontrado (ou soft-deletado)."},
    },
)
async def update_appointment(
    appointment_id: AppointmentIdPath,
    data: AppointmentUpdate,
    service: AppointmentServiceDep,
    current_user: CurrentUser,
) -> Appointment:
    """
    Atualiza campos de um agendamento (parcial). Toda chamada bem-sucedida
    grava, na mesma transação, uma linha em `appointment_history` — não é
    uma segunda chamada da aplicação, é uma function no próprio Postgres
    que garante que o `UPDATE` e o registro de auditoria acontecem juntos
    ou não acontecem. `updated_by_user_id` vem do usuário autenticado.
    """
    return await service.update(appointment_id, data, current_user)


@router.patch(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    summary="Reagendar agendamento",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Usuário não tem acesso à unidade deste cliente."},
        404: {"description": "Agendamento não encontrado (ou soft-deletado)."},
        409: {"description": "Este cliente já tem um agendamento ativo neste exato horário."},
    },
)
async def reschedule_appointment(
    appointment_id: AppointmentIdPath,
    data: AppointmentReschedule,
    service: AppointmentServiceDep,
    current_user: CurrentUser,
) -> Appointment:
    return await service.reschedule(appointment_id, data, current_user)


@router.delete(
    "/{appointment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir agendamento",
    responses={
        401: {"description": "Token ausente ou inválido."},
        403: {"description": "Usuário não tem acesso à unidade deste agendamento."},
        404: {"description": "Agendamento não encontrado (ou já soft-deletado)."},
    },
)
async def delete_appointment(
    appointment_id: AppointmentIdPath, service: AppointmentServiceDep, current_user: CurrentUser
) -> None:
    """
    Remove um agendamento (soft delete) — reservado para remoção
    administrativa (erro de cadastro, duplicata). Para um cancelamento
    de verdade, prefira `PUT` com `status: "cancelled"`, que mantém o
    registro visível e gera histórico.
    """
    await service.delete(appointment_id, current_user)
