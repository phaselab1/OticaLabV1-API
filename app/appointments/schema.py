from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.appointments.model import AppointmentStatus
from app.customers.schema import PHONE_PATTERN


class AppointmentCreate(BaseModel):
    lead_full_name: str = Field(
        max_length=255,
        description=(
            "Nome completo de quem está marcando o horário. Ainda não é um cliente — "
            "não gera linha em `customers` até o agendamento ser marcado `attended`."
        ),
        examples=["Bruno Souza"],
    )
    lead_phone: str | None = Field(
        default=None,
        pattern=PHONE_PATTERN,
        description="Telefone com DDD, só dígitos (10 ou 11 caracteres), sem máscara.",
        examples=["11987654321"],
    )
    scheduled_at: datetime = Field(
        description="Data e hora do agendamento (ISO 8601, com fuso). Status inicial: `scheduled`.",
        examples=["2026-06-15T14:30:00Z"],
    )
    notes: str | None = Field(
        default=None, max_length=2000, description="Observações livres sobre o agendamento."
    )
    company_id: str | None = Field(
        default=None,
        description=(
            "UUID da empresa. Obrigatório para `super_admin`; para os demais roles, "
            "preenchido automaticamente a partir do vínculo em `company_users` quando omitido "
            "(erro 400 se o usuário tiver acesso a mais de uma empresa e não especificar)."
        ),
    )
    company_unit_id: str | None = Field(
        default=None,
        description=(
            "UUID da unidade. Obrigatório para `super_admin` e para `admin`; para `manager`/"
            "`attendant` vinculados a exatamente uma unidade, preenchido automaticamente quando "
            "omitido (erro 400 se houver ambiguidade)."
        ),
    )


class AppointmentUpdate(BaseModel):
    scheduled_at: datetime | None = Field(
        default=None, description="Novo horário, se for reagendar."
    )
    status: AppointmentStatus | None = Field(
        default=None,
        description=(
            "Novo status, se for alterar. Marcar `attended` (compareceu) promove o lead a "
            "cliente de verdade: cria (ou reaproveita, se já existir pelo nome nesta empresa) "
            "a linha em `customers` e liga `customer_id` automaticamente."
        ),
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Novas observações. `null` limpa o campo; omitir mantém o valor atual.",
    )


class AppointmentReschedule(BaseModel):
    scheduled_at: datetime = Field(
        description="Nova data e hora do reagendamento (ISO 8601 com fuso)."
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Observações ou motivo do reagendamento.",
    )


class AppointmentResponse(BaseModel):
    id: str = Field(description="UUID do agendamento.")
    company_id: str
    company_unit_id: str
    lead_full_name: str = Field(description="Nome informado ao marcar o horário.")
    lead_phone: str | None = Field(description="Telefone informado ao marcar.")
    customer_id: str | None = Field(
        description=(
            "UUID do cliente, se o lead já foi promovido (agendamento marcado `attended` "
            "ao menos uma vez). Nulo enquanto ainda é só um lead."
        )
    )
    created_by_user_id: str = Field(description="UUID de quem criou o agendamento. Nunca muda.")
    updated_by_user_id: str | None = Field(
        description="UUID de quem fez a última alteração. Nulo até a primeira edição."
    )
    scheduled_at: datetime
    status: AppointmentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentHistoryResponse(BaseModel):
    id: str = Field(description="UUID da linha de histórico.")
    appointment_id: str
    changed_by_user_id: str = Field(description="UUID de quem fez esta alteração específica.")
    previous_scheduled_at: datetime | None = Field(description="Horário antes da alteração.")
    new_scheduled_at: datetime | None = Field(description="Horário depois da alteração.")
    previous_status: AppointmentStatus | None = Field(description="Status antes da alteração.")
    new_status: AppointmentStatus | None = Field(description="Status depois da alteração.")
    previous_notes: str | None = Field(description="Observações antes da alteração.")
    new_notes: str | None = Field(description="Observações depois da alteração.")
    changed_at: datetime = Field(description="Quando esta alteração ocorreu.")

    model_config = ConfigDict(from_attributes=True)
