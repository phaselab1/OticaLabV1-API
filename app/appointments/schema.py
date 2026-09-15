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
    scheduled_at: datetime
    status: AppointmentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
