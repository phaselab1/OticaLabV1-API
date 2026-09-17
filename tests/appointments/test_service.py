from datetime import UTC, datetime
from typing import Any

import pytest

from app.appointments.exceptions import AppointmentNotFoundError
from app.appointments.model import Appointment, AppointmentHistoryEntry, AppointmentStatus
from app.appointments.schema import AppointmentCreate, AppointmentUpdate
from app.appointments.service import AppointmentHistoryService, AppointmentService
from app.companies.model import CompanyUserLink
from app.companies.service import CompanyUserService
from app.core.exceptions import ForbiddenError
from app.customers.exceptions import CustomerAlreadyExistsError
from app.customers.model import Customer
from app.users.model import User, UserRole

COMPANY_ID = "company-a"
UNIT_ID = "unit-a1"
LEAD_NAME = "Ana Silva"


class FakeAppointmentRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.history: list[dict[str, Any]] = []

    async def create(self, data: dict[str, Any]) -> Appointment:
        appointment_id = str(len(self.rows) + 1)
        now = datetime.now(UTC).isoformat()
        row = {
            "id": appointment_id,
            "customer_id": None,
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
        customer_id: str | None = None,
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
        if customer_id is not None:
            row["customer_id"] = customer_id
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
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.simulate_race_once = False

    async def get_by_identity(self, *, company_id: str, full_name: str) -> Customer | None:
        for row in self.rows.values():
            if (
                row["deleted_at"] is None
                and row["company_id"] == company_id
                and row["full_name"] == full_name
            ):
                return Customer.from_row(row)
        return None

    async def create(self, data: dict[str, Any]) -> Customer:
        if self.simulate_race_once:
            self.simulate_race_once = False
            # A concurrent request already promoted this exact lead identity and
            # committed first — simulate the unique-constraint violation the real
            # repository would raise, after "someone else's" row lands in rows.
            now = datetime.now(UTC).isoformat()
            row = {
                "id": "race-winner",
                "updated_by_user_id": None,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
                **data,
            }
            self.rows["race-winner"] = row
            raise CustomerAlreadyExistsError(data["full_name"])

        customer_id = str(len(self.rows) + 1)
        now = datetime.now(UTC).isoformat()
        row = {
            "id": customer_id,
            "updated_by_user_id": None,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            **data,
        }
        self.rows[customer_id] = row
        return Customer.from_row(row)


class FakeCompanyUserRepository:
    def __init__(self, links: list[CompanyUserLink]) -> None:
        self.links = links

    async def get_all_for_user(self, user_id: str) -> list[CompanyUserLink]:
        return [link for link in self.links if link.user_id == user_id]


def _company_user_service(links: list[CompanyUserLink]) -> CompanyUserService:
    return CompanyUserService(
        FakeCompanyUserRepository(links),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
    )


def _link(user_id: str, company_id: str, unit_id: str | None) -> CompanyUserLink:
    now = datetime.now(UTC)
    return CompanyUserLink(
        id=f"{user_id}-{company_id}-{unit_id}",
        company_id=company_id,
        user_id=user_id,
        unit_id=unit_id,
        granted_by_user_id="granter",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


def _lead_create(**overrides: Any) -> AppointmentCreate:
    data = {
        "lead_full_name": LEAD_NAME,
        "scheduled_at": datetime.now(UTC),
        **overrides,
    }
    return AppointmentCreate(**data)


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
def customer_repository() -> FakeCustomerRepository:
    return FakeCustomerRepository()


@pytest.fixture
def service(
    appointment_repository: FakeAppointmentRepository,
    customer_repository: FakeCustomerRepository,
    current_user: User,
) -> AppointmentService:
    company_user_service = _company_user_service([_link(current_user.id, COMPANY_ID, UNIT_ID)])
    return AppointmentService(
        appointment_repository,  # type: ignore[arg-type]
        customer_repository,  # type: ignore[arg-type]
        company_user_service,
    )


async def test_create_appointment_as_lead(service: AppointmentService, current_user: User) -> None:
    created = await service.create(_lead_create(), current_user)

    assert created.lead_full_name == LEAD_NAME
    assert created.customer_id is None
    assert created.company_id == COMPANY_ID
    assert created.company_unit_id == UNIT_ID
    assert created.created_by_user_id == current_user.id
    assert created.status == AppointmentStatus.SCHEDULED


async def test_get_by_id_missing_raises_not_found(
    service: AppointmentService, current_user: User
) -> None:
    with pytest.raises(AppointmentNotFoundError):
        await service.get_by_id("missing", current_user)


async def test_create_appointment_without_unit_access_forbidden(
    appointment_repository: FakeAppointmentRepository,
    customer_repository: FakeCustomerRepository,
) -> None:
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
    service = AppointmentService(
        appointment_repository,  # type: ignore[arg-type]
        customer_repository,  # type: ignore[arg-type]
        _company_user_service([]),
    )

    with pytest.raises(ForbiddenError):
        await service.create(_lead_create(company_id=COMPANY_ID, company_unit_id=UNIT_ID), outsider)


async def test_update_status_cancelled_does_not_create_customer(
    service: AppointmentService,
    appointment_repository: FakeAppointmentRepository,
    customer_repository: FakeCustomerRepository,
    current_user: User,
) -> None:
    created = await service.create(_lead_create(), current_user)

    updated = await service.update(
        created.id, AppointmentUpdate(status=AppointmentStatus.CANCELLED), current_user
    )

    assert updated.status == AppointmentStatus.CANCELLED
    assert updated.customer_id is None
    assert customer_repository.rows == {}
    assert appointment_repository.history[0]["previous_status"] == AppointmentStatus.SCHEDULED.value


async def test_update_status_attended_promotes_lead_to_customer(
    service: AppointmentService,
    customer_repository: FakeCustomerRepository,
    current_user: User,
) -> None:
    created = await service.create(_lead_create(), current_user)

    updated = await service.update(
        created.id, AppointmentUpdate(status=AppointmentStatus.ATTENDED), current_user
    )

    assert updated.status == AppointmentStatus.ATTENDED
    assert updated.customer_id is not None
    customer = customer_repository.rows[updated.customer_id]
    assert customer["full_name"] == LEAD_NAME
    assert customer["company_id"] == COMPANY_ID
    assert customer["company_unit_id"] == UNIT_ID


async def test_update_status_attended_reuses_existing_customer(
    service: AppointmentService,
    customer_repository: FakeCustomerRepository,
    current_user: User,
) -> None:
    existing_customer = await customer_repository.create(
        {
            "company_id": COMPANY_ID,
            "company_unit_id": UNIT_ID,
            "full_name": LEAD_NAME,
            "phone": None,
            "created_by_user_id": current_user.id,
        }
    )

    created = await service.create(_lead_create(), current_user)
    updated = await service.update(
        created.id, AppointmentUpdate(status=AppointmentStatus.ATTENDED), current_user
    )

    assert updated.customer_id == existing_customer.id
    assert len(customer_repository.rows) == 1


async def test_update_status_attended_retries_after_concurrent_promotion_race(
    service: AppointmentService,
    customer_repository: FakeCustomerRepository,
    current_user: User,
) -> None:
    created = await service.create(_lead_create(), current_user)
    customer_repository.simulate_race_once = True

    updated = await service.update(
        created.id, AppointmentUpdate(status=AppointmentStatus.ATTENDED), current_user
    )

    assert updated.status == AppointmentStatus.ATTENDED
    assert updated.customer_id == "race-winner"
    assert len(customer_repository.rows) == 1


async def test_update_status_no_show_does_not_create_customer(
    service: AppointmentService,
    customer_repository: FakeCustomerRepository,
    current_user: User,
) -> None:
    created = await service.create(_lead_create(), current_user)

    updated = await service.update(
        created.id, AppointmentUpdate(status=AppointmentStatus.NO_SHOW), current_user
    )

    assert updated.status == AppointmentStatus.NO_SHOW
    assert updated.customer_id is None
    assert customer_repository.rows == {}


async def test_update_missing_appointment_raises_not_found(
    service: AppointmentService, current_user: User
) -> None:
    with pytest.raises(AppointmentNotFoundError):
        await service.update(
            "missing", AppointmentUpdate(status=AppointmentStatus.CANCELLED), current_user
        )


async def test_delete_then_get_by_id_raises_not_found(
    service: AppointmentService, current_user: User
) -> None:
    created = await service.create(_lead_create(), current_user)

    await service.delete(created.id, current_user)

    with pytest.raises(AppointmentNotFoundError):
        await service.get_by_id(created.id, current_user)


async def test_history_service_returns_entries_for_existing_appointment(
    service: AppointmentService,
    appointment_repository: FakeAppointmentRepository,
    current_user: User,
) -> None:
    created = await service.create(_lead_create(), current_user)
    await service.update(
        created.id, AppointmentUpdate(status=AppointmentStatus.CANCELLED), current_user
    )

    company_user_service = _company_user_service([_link(current_user.id, COMPANY_ID, UNIT_ID)])
    history_service = AppointmentHistoryService(
        FakeAppointmentHistoryRepository(appointment_repository),  # type: ignore[arg-type]
        appointment_repository,  # type: ignore[arg-type]
        company_user_service,
    )

    page = await history_service.get_by_appointment(created.id, current_user, page=1, page_size=20)

    assert page.total == 1
    assert page.items[0].new_status == AppointmentStatus.CANCELLED


async def test_history_service_unknown_appointment_raises_not_found(
    appointment_repository: FakeAppointmentRepository, current_user: User
) -> None:
    history_service = AppointmentHistoryService(
        FakeAppointmentHistoryRepository(appointment_repository),  # type: ignore[arg-type]
        appointment_repository,  # type: ignore[arg-type]
        _company_user_service([]),
    )

    with pytest.raises(AppointmentNotFoundError):
        await history_service.get_by_appointment("missing", current_user, page=1, page_size=20)
