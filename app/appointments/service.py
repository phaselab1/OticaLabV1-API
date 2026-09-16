from app.appointments.exceptions import AppointmentNotFoundError
from app.appointments.model import Appointment, AppointmentHistoryEntry, AppointmentStatus
from app.appointments.repository import AppointmentHistoryRepository, AppointmentRepository
from app.appointments.schema import AppointmentCreate, AppointmentReschedule, AppointmentUpdate
from app.companies.service import CompanyUserService
from app.core.exceptions import ForbiddenError
from app.customers.exceptions import CustomerNotFoundError
from app.customers.repository import CustomerRepository
from app.shared.pagination import Page
from app.users.model import User


class AppointmentService:
    def __init__(
        self,
        repository: AppointmentRepository,
        customer_repository: CustomerRepository,
        company_user_service: CompanyUserService,
    ) -> None:
        self.repository = repository
        self.customer_repository = customer_repository
        self.company_user_service = company_user_service

    async def create(self, data: AppointmentCreate, current_user: User) -> Appointment:
        customer = await self.customer_repository.get_by_id(data.customer_id)
        if customer is None:
            raise CustomerNotFoundError(data.customer_id)

        if not await self.company_user_service.has_unit_access(
            current_user, customer.company_id, customer.company_unit_id
        ):
            raise ForbiddenError(
                f"No access to unit {customer.company_unit_id} of company {customer.company_id}"
            )

        payload = data.model_dump(mode="json")
        payload["created_by_user_id"] = current_user.id
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

    async def update(
        self, appointment_id: str, data: AppointmentUpdate, current_user: User
    ) -> Appointment:
        existing = await self.get_by_id(appointment_id)
        customer = await self.customer_repository.get_by_id(existing.customer_id)
        if customer is not None and not await self.company_user_service.has_unit_access(
            current_user, customer.company_id, customer.company_unit_id
        ):
            raise ForbiddenError(
                f"No access to unit {customer.company_unit_id} of company {customer.company_id}"
            )

        payload = data.model_dump(mode="json", exclude_unset=True)
        appointment = await self.repository.update_with_history(
            appointment_id,
            current_user.id,
            scheduled_at=payload.get("scheduled_at"),
            status=payload.get("status"),
            notes=payload.get("notes"),
            notes_provided="notes" in payload,
        )
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        return appointment

    async def reschedule(
        self, appointment_id: str, data: AppointmentReschedule, current_user: User
    ) -> Appointment:
        existing = await self.get_by_id(appointment_id)
        customer = await self.customer_repository.get_by_id(existing.customer_id)
        if customer is not None and not await self.company_user_service.has_unit_access(
            current_user, customer.company_id, customer.company_unit_id
        ):
            raise ForbiddenError(
                f"No access to unit {customer.company_unit_id} of company {customer.company_id}"
            )

        payload = data.model_dump(mode="json")
        appointment = await self.repository.update_with_history(
            appointment_id,
            current_user.id,
            scheduled_at=payload["scheduled_at"],
            status=None,
            notes=payload.get("notes"),
            notes_provided="notes" in payload,
        )
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        return appointment

    async def delete(self, appointment_id: str) -> None:
        deleted = await self.repository.soft_delete(appointment_id)
        if not deleted:
            raise AppointmentNotFoundError(appointment_id)


class AppointmentHistoryService:
    def __init__(
        self,
        repository: AppointmentHistoryRepository,
        appointment_repository: AppointmentRepository,
    ) -> None:
        self.repository = repository
        self.appointment_repository = appointment_repository

    async def get_by_appointment(
        self, appointment_id: str, *, page: int, page_size: int
    ) -> Page[AppointmentHistoryEntry]:
        appointment = await self.appointment_repository.get_by_id(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)

        entries, total = await self.repository.get_by_appointment_id(
            appointment_id, page=page, page_size=page_size
        )
        return Page(items=entries, page=page, page_size=page_size, total=total)
