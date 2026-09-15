from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.appointments.model import AppointmentStatus


class AppointmentCreate(BaseModel):
    customer_id: str
    scheduled_at: datetime
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    scheduled_at: datetime | None = None
    status: AppointmentStatus | None = None
    notes: str | None = None


class AppointmentResponse(BaseModel):
    id: str
    customer_id: str
    created_by_user_id: str
    updated_by_user_id: str | None
    scheduled_at: datetime
    status: AppointmentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentHistoryResponse(BaseModel):
    id: str
    appointment_id: str
    changed_by_user_id: str
    previous_scheduled_at: datetime | None
    new_scheduled_at: datetime | None
    previous_status: AppointmentStatus | None
    new_status: AppointmentStatus | None
    previous_notes: str | None
    new_notes: str | None
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)
