from datetime import UTC, datetime
from typing import Any

import pytest

from app.appointments.exceptions import AppointmentNotFoundError
from app.appointments.model import Appointment, AppointmentStatus
from app.appointments.schema import AppointmentCreate, AppointmentUpdate
from app.appointments.service import AppointmentService
from app.customers.exceptions import CustomerNotFoundError
from app.customers.model import Customer


class FakeAppointmentRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def create(self, data: dict[str, Any]) -> Appointment:
        appointment_id = str(len(self.rows) + 1)
        now = datetime.now(UTC).isoformat()
        row = {
            "id": appointment_id,
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

    async def update(self, appointment_id: str, data: dict[str, Any]) -> Appointment | None:
        row = self.rows.get(appointment_id)
        if row is None or row["deleted_at"] is not None:
            return None
        row.update(data)
        return Appointment.from_row(row)

    async def soft_delete(self, appointment_id: str) -> bool:
        row = self.rows.get(appointment_id)
        if row is None or row["deleted_at"] is not None:
            return False
        row["deleted_at"] = datetime.now(UTC).isoformat()
        return True


class FakeCustomerRepository:
    def __init__(self, known_customer_ids: set[str]) -> None:
        self.known_customer_ids = known_customer_ids

    async def get_by_id(self, customer_id: str) -> Customer | None:
        if customer_id not in self.known_customer_ids:
            return None
        now = datetime.now(UTC)
        return Customer(
            id=customer_id,
            full_name="Ana Silva",
            date_of_birth=now.date(),
            phone=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )


@pytest.fixture
def service() -> AppointmentService:
    return AppointmentService(
        FakeAppointmentRepository(),  # type: ignore[arg-type]
        FakeCustomerRepository({"customer-1"}),  # type: ignore[arg-type]
    )


async def test_create_appointment_for_known_customer(service: AppointmentService) -> None:
    created = await service.create(
        AppointmentCreate(customer_id="customer-1", scheduled_at=datetime.now(UTC))
    )

    assert created.customer_id == "customer-1"
    assert created.status == AppointmentStatus.SCHEDULED


async def test_create_appointment_for_unknown_customer_raises(
    service: AppointmentService,
) -> None:
    with pytest.raises(CustomerNotFoundError):
        await service.create(
            AppointmentCreate(customer_id="missing", scheduled_at=datetime.now(UTC))
        )


async def test_get_by_id_missing_raises_not_found(service: AppointmentService) -> None:
    with pytest.raises(AppointmentNotFoundError):
        await service.get_by_id("missing")


async def test_update_status(service: AppointmentService) -> None:
    created = await service.create(
        AppointmentCreate(customer_id="customer-1", scheduled_at=datetime.now(UTC))
    )

    updated = await service.update(
        created.id, AppointmentUpdate(status=AppointmentStatus.CONFIRMED)
    )

    assert updated.status == AppointmentStatus.CONFIRMED


async def test_delete_then_get_by_id_raises_not_found(service: AppointmentService) -> None:
    created = await service.create(
        AppointmentCreate(customer_id="customer-1", scheduled_at=datetime.now(UTC))
    )

    await service.delete(created.id)

    with pytest.raises(AppointmentNotFoundError):
        await service.get_by_id(created.id)
