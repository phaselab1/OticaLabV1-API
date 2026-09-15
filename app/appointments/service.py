from app.appointments.exceptions import AppointmentNotFoundError
from app.appointments.model import Appointment, AppointmentStatus
from app.appointments.repository import AppointmentRepository
from app.appointments.schema import AppointmentCreate, AppointmentUpdate
from app.customers.exceptions import CustomerNotFoundError
from app.customers.repository import CustomerRepository
from app.shared.pagination import Page


class AppointmentService:
    def __init__(
        self, repository: AppointmentRepository, customer_repository: CustomerRepository
    ) -> None:
        self.repository = repository
        self.customer_repository = customer_repository

    async def create(self, data: AppointmentCreate) -> Appointment:
        customer = await self.customer_repository.get_by_id(data.customer_id)
        if customer is None:
            raise CustomerNotFoundError(data.customer_id)

        payload = data.model_dump(mode="json")
        return await self.repository.create(payload)

    async def get_all(
        self,
        *,
        page: int,
        page_size: int,
        customer_id: str | None = None,
        status: AppointmentStatus | None = None,
    ) -> Page[Appointment]:
        appointments, total = await self.repository.get_all(
            page=page, page_size=page_size, customer_id=customer_id, status=status
        )
        return Page(items=appointments, page=page, page_size=page_size, total=total)

    async def get_by_id(self, appointment_id: str) -> Appointment:
        appointment = await self.repository.get_by_id(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        return appointment

    async def update(self, appointment_id: str, data: AppointmentUpdate) -> Appointment:
        payload = data.model_dump(mode="json", exclude_unset=True)
        appointment = await self.repository.update(appointment_id, payload)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        return appointment

    async def delete(self, appointment_id: str) -> None:
        deleted = await self.repository.soft_delete(appointment_id)
        if not deleted:
            raise AppointmentNotFoundError(appointment_id)
