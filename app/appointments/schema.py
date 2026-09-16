from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.appointments.model import AppointmentStatus


class AppointmentCreate(BaseModel):
    customer_id: str = Field(description="UUID do cliente. Deve estar ativo (não soft-deletado).")
    scheduled_at: datetime = Field(
        description="Data e hora do agendamento (ISO 8601, com fuso). Status inicial: `scheduled`.",
        examples=["2026-06-15T14:30:00Z"],
    )
    notes: str | None = Field(default=None, description="Observações livres sobre o agendamento.")


class AppointmentUpdate(BaseModel):
    scheduled_at: datetime | None = Field(
        default=None, description="Novo horário, se for reagendar."
    )
    status: AppointmentStatus | None = Field(
        default=None, description="Novo status, se for alterar."
    )
    notes: str | None = Field(
        default=None,
        description="Novas observações. `null` limpa o campo; omitir mantém o valor atual.",
    )


class AppointmentReschedule(BaseModel):
    scheduled_at: datetime = Field(
        description="Nova data e hora do reagendamento (ISO 8601 com fuso)."
    )
    notes: str | None = Field(
        default=None,
        description="Observações ou motivo do reagendamento.",
    )


class AppointmentResponse(BaseModel):
    id: str = Field(description="UUID do agendamento.")
    customer_id: str
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
