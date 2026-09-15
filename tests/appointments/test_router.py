from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.appointments.dependencies import get_appointment_service
from app.appointments.exceptions import AppointmentNotFoundError
from app.appointments.model import Appointment, AppointmentStatus
from app.appointments.schema import AppointmentCreate, AppointmentUpdate
from app.customers.exceptions import CustomerNotFoundError
from app.main import app
from app.shared.pagination import Page


class FakeAppointmentService:
    def __init__(self) -> None:
        self.rows: dict[str, Appointment] = {}
        self.known_customer_ids = {"customer-1"}

    async def create(self, data: AppointmentCreate) -> Appointment:
        if data.customer_id not in self.known_customer_ids:
            raise CustomerNotFoundError(data.customer_id)

        now = datetime.now(UTC)
        appointment = Appointment(
            id=str(len(self.rows) + 1),
            customer_id=data.customer_id,
            scheduled_at=data.scheduled_at,
            status=AppointmentStatus.SCHEDULED,
            notes=data.notes,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.rows[appointment.id] = appointment
        return appointment

    async def get_all(self, **_: object) -> Page[Appointment]:
        items = list(self.rows.values())
        return Page(items=items, page=1, page_size=20, total=len(items))

    async def get_by_id(self, appointment_id: str) -> Appointment:
        appointment = self.rows.get(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        return appointment

    async def update(self, appointment_id: str, data: AppointmentUpdate) -> Appointment:
        appointment = await self.get_by_id(appointment_id)
        updated = replace(appointment, **data.model_dump(exclude_unset=True))
        self.rows[appointment_id] = updated
        return updated

    async def delete(self, appointment_id: str) -> None:
        await self.get_by_id(appointment_id)
        del self.rows[appointment_id]


@pytest.fixture
def client() -> TestClient:
    fake_service = FakeAppointmentService()
    app.dependency_overrides[get_appointment_service] = lambda: fake_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_appointment_for_known_customer(client: TestClient) -> None:
    response = client.post(
        "/appointments/",
        json={"customer_id": "customer-1", "scheduled_at": "2026-01-01T10:00:00Z"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "scheduled"


def test_create_appointment_for_unknown_customer(client: TestClient) -> None:
    response = client.post(
        "/appointments/",
        json={"customer_id": "missing", "scheduled_at": "2026-01-01T10:00:00Z"},
    )

    assert response.status_code == 404


def test_get_appointment_not_found(client: TestClient) -> None:
    response = client.get("/appointments/missing")

    assert response.status_code == 404


def test_update_appointment_status(client: TestClient) -> None:
    created = client.post(
        "/appointments/",
        json={"customer_id": "customer-1", "scheduled_at": "2026-01-01T10:00:00Z"},
    ).json()

    updated = client.put(f"/appointments/{created['id']}", json={"status": "confirmed"})

    assert updated.status_code == 200
    assert updated.json()["status"] == "confirmed"
