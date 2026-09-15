from typing import Annotated

from fastapi import APIRouter, Query, status

from app.appointments.dependencies import AppointmentHistoryServiceDep, AppointmentServiceDep
from app.appointments.model import Appointment, AppointmentHistoryEntry, AppointmentStatus
from app.appointments.schema import (
    AppointmentCreate,
    AppointmentHistoryResponse,
    AppointmentResponse,
    AppointmentUpdate,
)
from app.shared.pagination import Page
from app.users.dependencies import CurrentUser

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    data: AppointmentCreate, service: AppointmentServiceDep, current_user: CurrentUser
) -> Appointment:
    return await service.create(data, current_user)


@router.get("/", response_model=Page[AppointmentResponse])
async def list_appointments(
    service: AppointmentServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    customer_id: Annotated[str | None, Query()] = None,
    status_filter: Annotated[AppointmentStatus | None, Query(alias="status")] = None,
) -> Page[Appointment]:
    return await service.get_all(
        page=page, page_size=page_size, customer_id=customer_id, status=status_filter
    )


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(appointment_id: str, service: AppointmentServiceDep) -> Appointment:
    return await service.get_by_id(appointment_id)


@router.get("/{appointment_id}/history", response_model=Page[AppointmentHistoryResponse])
async def list_appointment_history(
    appointment_id: str,
    service: AppointmentHistoryServiceDep,
    _current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[AppointmentHistoryEntry]:
    return await service.get_by_appointment(appointment_id, page=page, page_size=page_size)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: str,
    data: AppointmentUpdate,
    service: AppointmentServiceDep,
    current_user: CurrentUser,
) -> Appointment:
    return await service.update(appointment_id, data, current_user)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(
    appointment_id: str, service: AppointmentServiceDep, _current_user: CurrentUser
) -> None:
    await service.delete(appointment_id)
