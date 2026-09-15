from typing import Annotated

from fastapi import Depends

from app.appointments.repository import AppointmentRepository
from app.appointments.service import AppointmentService
from app.core.dependencies import SupabaseClient
from app.customers.dependencies import get_customer_repository
from app.customers.repository import CustomerRepository


def get_appointment_repository(db: SupabaseClient) -> AppointmentRepository:
    return AppointmentRepository(db)


def get_appointment_service(
    repository: Annotated[AppointmentRepository, Depends(get_appointment_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> AppointmentService:
    return AppointmentService(repository, customer_repository)


AppointmentServiceDep = Annotated[AppointmentService, Depends(get_appointment_service)]
