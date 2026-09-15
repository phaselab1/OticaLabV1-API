from datetime import UTC, datetime
from typing import Any

import pytest

from app.appointments.exceptions import AppointmentNotFoundError
from app.appointments.model import Appointment, AppointmentHistoryEntry, AppointmentStatus
from app.appointments.schema import AppointmentCreate, AppointmentUpdate
from app.appointments.service import AppointmentHistoryService, AppointmentService
from app.companies.model import CompanyUserLink
from app.companies.service import CompanyUserService
from app.customers.exceptions import CustomerNotFoundError
from app.customers.model import Customer
from app.users.model import User, UserRole

COMPANY_ID = "company-a"
UNIT_ID = "unit-a1"


class FakeAppointmentRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.history: list[dict[str, Any]] = []

    async def create(self, data: dict[str, Any]) -> Appointment:
        appointment_id = str(len(self.rows) + 1)
        now = datetime.now(UTC).isoformat()
        row = {
            "id": appointment_id,
            "updated_by_user_id": None,
            "status": AppointmentStatus.SCHEDULED.value,
            "notes": None,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            **data,
        }
        self.rows[appointment_id] = row
        return Appointment.from_row(row)

    async def get_by_id(self, appointment_id: str) -> Appointment | None:
        row = self.rows.get(appointment_id)
        if row is None or row["deleted_at"] is not None:
            return None
        return Appointment.from_row(row)

    async def update_with_history(
        self,
        appointment_id: str,
        changed_by_user_id: str,
        *,
        scheduled_at: str | None,
        status: str | None,
        notes: str | None,
        notes_provided: bool,
    ) -> Appointment | None:
        row = self.rows.get(appointment_id)
        if row is None or row["deleted_at"] is not None:
            return None

        previous = dict(row)
        if scheduled_at is not None:
            row["scheduled_at"] = scheduled_at
        if status is not None:
            row["status"] = status
        if notes_provided:
            row["notes"] = notes
        row["updated_by_user_id"] = changed_by_user_id

        self.history.append(
            {
                "id": str(len(self.history) + 1),
                "appointment_id": appointment_id,
                "changed_by_user_id": changed_by_user_id,
                "previous_scheduled_at": previous["scheduled_at"],
                "new_scheduled_at": row["scheduled_at"],
                "previous_status": previous["status"],
                "new_status": row["status"],
                "previous_notes": previous["notes"],
                "new_notes": row["notes"],
                "changed_at": datetime.now(UTC).isoformat(),
            }
        )
        return Appointment.from_row(row)

    async def soft_delete(self, appointment_id: str) -> bool:
        row = self.rows.get(appointment_id)
        if row is None or row["deleted_at"] is not None:
            return False
        row["deleted_at"] = datetime.now(UTC).isoformat()
        return True


class FakeAppointmentHistoryRepository:
    def __init__(self, appointment_repository: FakeAppointmentRepository) -> None:
        self.appointment_repository = appointment_repository

    async def get_by_appointment_id(
        self, appointment_id: str, *, page: int, page_size: int
    ) -> tuple[list[AppointmentHistoryEntry], int]:
        entries = [
            AppointmentHistoryEntry.from_row(row)
            for row in self.appointment_repository.history
            if row["appointment_id"] == appointment_id
        ]
        return entries, len(entries)


class FakeCustomerRepository:
    def __init__(self, known_customer_ids: set[str]) -> None:
        self.known_customer_ids = known_customer_ids

    async def get_by_id(self, customer_id: str) -> Customer | None:
        if customer_id not in self.known_customer_ids:
            return None
        now = datetime.now(UTC)
        return Customer(
            id=customer_id,
            company_id=COMPANY_ID,
            company_unit_id=UNIT_ID,
            full_name="Ana Silva",
            date_of_birth=now.date(),
            phone=None,
            created_by_user_id="user-1",
            updated_by_user_id=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )


class FakeCompanyUserRepository:
    def __init__(self, links: list[CompanyUserLink]) -> None:
        self.links = links

    async def get_all_for_user(self, user_id: str) -> list[CompanyUserLink]:
        return [link for link in self.links if link.user_id == user_id]


@pytest.fixture
def current_user() -> User:
    now = datetime.now(UTC)
    return User(
        id="user-1",
        full_name="Atendente",
        email="atendente@example.com",
        password_hash="hash",
        role=UserRole.ATTENDANT,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


@pytest.fixture
def appointment_repository() -> FakeAppointmentRepository:
    return FakeAppointmentRepository()


@pytest.fixture
def service(
    appointment_repository: FakeAppointmentRepository, current_user: User
) -> AppointmentService:
    now = datetime.now(UTC)
    link = CompanyUserLink(
        id="link-1",
        company_id=COMPANY_ID,
        user_id=current_user.id,
        unit_id=UNIT_ID,
        granted_by_user_id="granter",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    company_user_service = CompanyUserService(
        FakeCompanyUserRepository([link]),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
    )
    return AppointmentService(
        appointment_repository,  # type: ignore[arg-type]
        FakeCustomerRepository({"customer-1"}),  # type: ignore[arg-type]
        company_user_service,
    )


async def test_create_appointment_for_known_customer(
    service: AppointmentService, current_user: User
) -> None:
    created = await service.create(
        AppointmentCreate(customer_id="customer-1", scheduled_at=datetime.now(UTC)), current_user
    )

    assert created.customer_id == "customer-1"
    assert created.created_by_user_id == current_user.id
    assert created.status == AppointmentStatus.SCHEDULED


async def test_create_appointment_for_unknown_customer_raises(
    service: AppointmentService, current_user: User
) -> None:
    with pytest.raises(CustomerNotFoundError):
        await service.create(
            AppointmentCreate(customer_id="missing", scheduled_at=datetime.now(UTC)), current_user
        )


async def test_get_by_id_missing_raises_not_found(service: AppointmentService) -> None:
    with pytest.raises(AppointmentNotFoundError):
        await service.get_by_id("missing")


async def test_create_appointment_without_unit_access_forbidden(
    appointment_repository: FakeAppointmentRepository,
) -> None:
    from app.core.exceptions import ForbiddenError

    now = datetime.now(UTC)
    outsider = User(
        id="user-2",
        full_name="Outsider",
        email="outsider@example.com",
        password_hash="hash",
        role=UserRole.ATTENDANT,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    company_user_service = CompanyUserService(
        FakeCompanyUserRepository([]),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
    )
    service = AppointmentService(
        appointment_repository,  # type: ignore[arg-type]
        FakeCustomerRepository({"customer-1"}),  # type: ignore[arg-type]
        company_user_service,
    )

    with pytest.raises(ForbiddenError):
        await service.create(
            AppointmentCreate(customer_id="customer-1", scheduled_at=datetime.now(UTC)), outsider
        )


async def test_update_status_records_history(
    service: AppointmentService,
    appointment_repository: FakeAppointmentRepository,
    current_user: User,
) -> None:
    created = await service.create(
        AppointmentCreate(customer_id="customer-1", scheduled_at=datetime.now(UTC)), current_user
    )

    updated = await service.update(
        created.id, AppointmentUpdate(status=AppointmentStatus.CONFIRMED), current_user
    )

    assert updated.status == AppointmentStatus.CONFIRMED
    assert updated.updated_by_user_id == current_user.id
    assert len(appointment_repository.history) == 1
    assert appointment_repository.history[0]["previous_status"] == AppointmentStatus.SCHEDULED.value
    assert appointment_repository.history[0]["new_status"] == AppointmentStatus.CONFIRMED.value


async def test_update_missing_appointment_raises_not_found(
    service: AppointmentService, current_user: User
) -> None:
    with pytest.raises(AppointmentNotFoundError):
        await service.update(
            "missing", AppointmentUpdate(status=AppointmentStatus.CONFIRMED), current_user
        )


async def test_delete_then_get_by_id_raises_not_found(
    service: AppointmentService, current_user: User
) -> None:
    created = await service.create(
        AppointmentCreate(customer_id="customer-1", scheduled_at=datetime.now(UTC)), current_user
    )

    await service.delete(created.id)

    with pytest.raises(AppointmentNotFoundError):
        await service.get_by_id(created.id)


async def test_history_service_returns_entries_for_existing_appointment(
    service: AppointmentService,
    appointment_repository: FakeAppointmentRepository,
    current_user: User,
) -> None:
    created = await service.create(
        AppointmentCreate(customer_id="customer-1", scheduled_at=datetime.now(UTC)), current_user
    )
    await service.update(
        created.id, AppointmentUpdate(status=AppointmentStatus.CONFIRMED), current_user
    )

    history_service = AppointmentHistoryService(
        FakeAppointmentHistoryRepository(appointment_repository),  # type: ignore[arg-type]
        appointment_repository,  # type: ignore[arg-type]
    )

    page = await history_service.get_by_appointment(created.id, page=1, page_size=20)

    assert page.total == 1
    assert page.items[0].new_status == AppointmentStatus.CONFIRMED


async def test_history_service_unknown_appointment_raises_not_found(
    appointment_repository: FakeAppointmentRepository,
) -> None:
    history_service = AppointmentHistoryService(
        FakeAppointmentHistoryRepository(appointment_repository),  # type: ignore[arg-type]
        appointment_repository,  # type: ignore[arg-type]
    )

    with pytest.raises(AppointmentNotFoundError):
        await history_service.get_by_appointment("missing", page=1, page_size=20)
