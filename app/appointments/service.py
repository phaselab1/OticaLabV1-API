from app.appointments.exceptions import AppointmentNotFoundError
from app.appointments.model import Appointment, AppointmentHistoryEntry, AppointmentStatus
from app.appointments.repository import AppointmentHistoryRepository, AppointmentRepository
from app.appointments.schema import AppointmentCreate, AppointmentReschedule, AppointmentUpdate
from app.companies.service import CompanyUserService
from app.core.exceptions import ForbiddenError
from app.customers.exceptions import CustomerAlreadyExistsError
from app.customers.repository import CustomerRepository
from app.shared.pagination import Page
from app.shared.utils.text import format_title_case
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
        company_id, company_unit_id = await self.company_user_service.resolve_company_and_unit(
            current_user, data.company_id, data.company_unit_id
        )

        payload = data.model_dump(mode="json", exclude={"company_id", "company_unit_id"})
        payload["lead_full_name"] = format_title_case(payload["lead_full_name"])
        payload["company_id"] = company_id
        payload["company_unit_id"] = company_unit_id
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
        company_id: str | None = None
        company_unit_id: str | None = None

        if current_user.role != UserRole.SUPER_ADMIN:
            company_id, company_unit_id = await self.company_user_service.resolve_company_and_unit(
                current_user, None, None
            )

        appointments, total = await self.repository.get_all(
            page=page,
            page_size=page_size,
            company_id=company_id,
            company_unit_id=company_unit_id,
            customer_id=customer_id,
            status=status,
        )
        return Page(items=appointments, page=page, page_size=page_size, total=total)

    async def _get_with_access_check(self, appointment_id: str, current_user: User) -> Appointment:
        appointment = await self.repository.get_by_id(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)

        if current_user.role == UserRole.SUPER_ADMIN:
            return appointment

        if not await self.company_user_service.has_unit_access(
            current_user, appointment.company_id, appointment.company_unit_id
        ):
            raise ForbiddenError(
                f"No access to unit {appointment.company_unit_id} "
                f"of company {appointment.company_id}"
            )
        return appointment

    async def get_by_id(self, appointment_id: str, current_user: User) -> Appointment:
        return await self._get_with_access_check(appointment_id, current_user)

    async def _promote_lead_to_customer(self, appointment: Appointment, current_user: User) -> str:
        """Vira o lead do agendamento em cliente de verdade (ou reaproveita um já existente
        com o mesmo nome nesta empresa), na primeira vez que o agendamento é marcado como
        `attended`."""
        existing_customer = await self.customer_repository.get_by_identity(
            company_id=appointment.company_id,
            full_name=appointment.lead_full_name,
        )
        if existing_customer is not None:
            return existing_customer.id

        try:
            customer = await self.customer_repository.create(
                {
                    "company_id": appointment.company_id,
                    "company_unit_id": appointment.company_unit_id,
                    "full_name": appointment.lead_full_name,
                    "phone": appointment.lead_phone,
                    "created_by_user_id": current_user.id,
                }
            )
        except CustomerAlreadyExistsError:
            # Lost a race against a concurrent promotion of the same lead identity
            # (check-then-create isn't atomic across two PostgREST calls) — the
            # winner's row is already committed and visible, so just use it.
            existing_customer = await self.customer_repository.get_by_identity(
                company_id=appointment.company_id,
                full_name=appointment.lead_full_name,
            )
            if existing_customer is None:
                raise
            return existing_customer.id
        return customer.id

    async def update(
        self, appointment_id: str, data: AppointmentUpdate, current_user: User
    ) -> Appointment:
        existing = await self._get_with_access_check(appointment_id, current_user)

        if (
            existing.status == AppointmentStatus.ATTENDED
            and current_user.role == UserRole.ATTENDANT
        ):
            raise ForbiddenError(
                "Agendamento já marcado como comparecido não pode ser alterado por atendente."
            )

        payload = data.model_dump(mode="json", exclude_unset=True)

        if (
            (existing.customer_id is not None or existing.status == AppointmentStatus.ATTENDED)
            and ("lead_full_name" in payload or "lead_phone" in payload)
        ):
            raise ForbiddenError(
                "Nome e telefone só podem ser alterados enquanto o agendamento não for cliente."
            )

        if "lead_full_name" in payload or "lead_phone" in payload:
            new_lead_name = (
                format_title_case(payload["lead_full_name"])
                if "lead_full_name" in payload and payload["lead_full_name"] is not None
                else None
            )
            await self.repository.update_lead_info(
                appointment_id,
                current_user.id,
                lead_full_name=new_lead_name,
                lead_phone=payload.get("lead_phone"),
                lead_phone_provided="lead_phone" in payload,
            )

        customer_id = None
        if (
            payload.get("status") == AppointmentStatus.ATTENDED.value
            and existing.customer_id is None
        ):
            customer_id = await self._promote_lead_to_customer(existing, current_user)

        subject = existing.lead_full_name or f"o cliente {existing.customer_id}"
        appointment = await self.repository.update_with_history(
            appointment_id,
            current_user.id,
            scheduled_at=payload.get("scheduled_at"),
            status=payload.get("status"),
            notes=payload.get("notes"),
            notes_provided="notes" in payload,
            customer_id=customer_id,
            subject=subject,
        )
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        return appointment

    async def reschedule(
        self, appointment_id: str, data: AppointmentReschedule, current_user: User
    ) -> Appointment:
        existing = await self._get_with_access_check(appointment_id, current_user)

        if (
            existing.status == AppointmentStatus.ATTENDED
            and current_user.role == UserRole.ATTENDANT
        ):
            raise ForbiddenError(
                "Agendamento já marcado como comparecido não pode ser reagendado por atendente."
            )

        payload = data.model_dump(mode="json")
        subject = existing.lead_full_name or f"o cliente {existing.customer_id}"
        appointment = await self.repository.update_with_history(
            appointment_id,
            current_user.id,
            scheduled_at=payload["scheduled_at"],
            status=None,
            notes=payload.get("notes"),
            notes_provided="notes" in payload,
            subject=subject,
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
        company_user_service: CompanyUserService,
    ) -> None:
        self.repository = repository
        self.appointment_repository = appointment_repository
        self.company_user_service = company_user_service

    async def get_by_appointment(
        self, appointment_id: str, current_user: User, *, page: int, page_size: int
    ) -> Page[AppointmentHistoryEntry]:
        appointment = await self.appointment_repository.get_by_id(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)

        if not await self.company_user_service.has_unit_access(
            current_user, appointment.company_id, appointment.company_unit_id
        ):
            raise ForbiddenError(
                f"No access to unit {appointment.company_unit_id} "
                f"of company {appointment.company_id}"
            )

        entries, total = await self.repository.get_by_appointment_id(
            appointment_id, page=page, page_size=page_size
        )
        return Page(items=entries, page=page, page_size=page_size, total=total)
