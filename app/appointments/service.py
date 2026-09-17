from app.appointments.exceptions import AppointmentNotFoundError
from app.appointments.model import Appointment, AppointmentHistoryEntry, AppointmentStatus
from app.appointments.repository import AppointmentHistoryRepository, AppointmentRepository
from app.appointments.schema import AppointmentCreate, AppointmentReschedule, AppointmentUpdate
from app.companies.service import CompanyUserService
from app.core.exceptions import ForbiddenError
from app.customers.exceptions import CustomerNotFoundError
from app.customers.repository import CustomerRepository
from app.shared.pagination import Page
from app.users.model import User, UserRole


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
        current_user: User,
        *,
        page: int,
        page_size: int,
        customer_id: str | None = None,
        status: AppointmentStatus | None = None,
    ) -> Page[Appointment]:
        customer_ids: list[str] | None = None

        if current_user.role != UserRole.SUPER_ADMIN:
            if customer_id is not None:
                customer = await self.customer_repository.get_by_id(customer_id)
                if customer is None or not await self.company_user_service.has_unit_access(
                    current_user, customer.company_id, customer.company_unit_id
                ):
                    raise ForbiddenError(f"No access to customer {customer_id}")
            else:
                (
                    company_id,
                    company_unit_id,
                ) = await self.company_user_service.resolve_company_and_unit(
                    current_user, None, None
                )
                customer_ids = await self.customer_repository.get_ids_by_scope(
                    company_id=company_id, company_unit_id=company_unit_id
                )

        appointments, total = await self.repository.get_all(
            page=page,
            page_size=page_size,
            customer_id=customer_id,
            customer_ids=customer_ids,
            status=status,
        )
        return Page(items=appointments, page=page, page_size=page_size, total=total)

    async def _get_with_access_check(self, appointment_id: str, current_user: User) -> Appointment:
        appointment = await self.repository.get_by_id(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)

        customer = await self.customer_repository.get_by_id(appointment.customer_id)
        if customer is not None and not await self.company_user_service.has_unit_access(
            current_user, customer.company_id, customer.company_unit_id
        ):
            raise ForbiddenError(
                f"No access to unit {customer.company_unit_id} of company {customer.company_id}"
            )
        return appointment

    async def get_by_id(self, appointment_id: str, current_user: User) -> Appointment:
        return await self._get_with_access_check(appointment_id, current_user)

    async def update(
        self, appointment_id: str, data: AppointmentUpdate, current_user: User
    ) -> Appointment:
        await self._get_with_access_check(appointment_id, current_user)

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
        await self._get_with_access_check(appointment_id, current_user)

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

    async def delete(self, appointment_id: str, current_user: User) -> None:
        await self._get_with_access_check(appointment_id, current_user)
        deleted = await self.repository.soft_delete(appointment_id)
        if not deleted:
            raise AppointmentNotFoundError(appointment_id)


class AppointmentHistoryService:
    def __init__(
        self,
        repository: AppointmentHistoryRepository,
        appointment_repository: AppointmentRepository,
        customer_repository: CustomerRepository,
        company_user_service: CompanyUserService,
    ) -> None:
        self.repository = repository
        self.appointment_repository = appointment_repository
        self.customer_repository = customer_repository
        self.company_user_service = company_user_service

    async def get_by_appointment(
        self, appointment_id: str, current_user: User, *, page: int, page_size: int
    ) -> Page[AppointmentHistoryEntry]:
        appointment = await self.appointment_repository.get_by_id(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)

        customer = await self.customer_repository.get_by_id(appointment.customer_id)
        if customer is not None and not await self.company_user_service.has_unit_access(
            current_user, customer.company_id, customer.company_unit_id
        ):
            raise ForbiddenError(
                f"No access to unit {customer.company_unit_id} of company {customer.company_id}"
            )

        entries, total = await self.repository.get_by_appointment_id(
            appointment_id, page=page, page_size=page_size
        )
        return Page(items=entries, page=page, page_size=page_size, total=total)
