from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.appointments.dependencies import get_appointment_history_service, get_appointment_service
from app.appointments.exceptions import AppointmentNotFoundError
from app.appointments.model import Appointment, AppointmentHistoryEntry, AppointmentStatus
from app.appointments.schema import AppointmentCreate, AppointmentUpdate
from app.customers.exceptions import CustomerNotFoundError
from app.main import app
from app.shared.pagination import Page
from app.users.dependencies import get_current_user
from app.users.model import User, UserRole


def _fake_user() -> User:
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


class FakeAppointmentService:
    def __init__(self) -> None:
        self.rows: dict[str, Appointment] = {}
        self.known_customer_ids = {"customer-1"}

    async def create(self, data: AppointmentCreate, current_user: User) -> Appointment:
        if data.customer_id not in self.known_customer_ids:
            raise CustomerNotFoundError(data.customer_id)

        now = datetime.now(UTC)
        appointment = Appointment(
            id=str(len(self.rows) + 1),
            customer_id=data.customer_id,
            created_by_user_id=current_user.id,
            updated_by_user_id=None,
            scheduled_at=data.scheduled_at,
            status=AppointmentStatus.SCHEDULED,
            notes=data.notes,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.rows[appointment.id] = appointment
        return appointment

    async def get_all(self, _current_user: User, **_: object) -> Page[Appointment]:
        items = list(self.rows.values())
        return Page(items=items, page=1, page_size=20, total=len(items))

    async def get_by_id(self, appointment_id: str, _current_user: User) -> Appointment:
        appointment = self.rows.get(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        return appointment

    async def update(
        self, appointment_id: str, data: AppointmentUpdate, current_user: User
    ) -> Appointment:
        appointment = await self.get_by_id(appointment_id, current_user)
        changes = data.model_dump(exclude_unset=True)
        updated = replace(appointment, updated_by_user_id=current_user.id, **changes)
        self.rows[appointment_id] = updated
        return updated

    async def delete(self, appointment_id: str, current_user: User) -> None:
        await self.get_by_id(appointment_id, current_user)
        del self.rows[appointment_id]


class FakeAppointmentHistoryService:
    async def get_by_appointment(
        self, appointment_id: str, _current_user: User, *, page: int, page_size: int
    ) -> Page[AppointmentHistoryEntry]:
        if appointment_id != "with-history":
            raise AppointmentNotFoundError(appointment_id)

        now = datetime.now(UTC)
        entry = AppointmentHistoryEntry(
            id="1",
            appointment_id=appointment_id,
            changed_by_user_id="user-1",
            previous_scheduled_at=now,
            new_scheduled_at=now,
            previous_status=AppointmentStatus.SCHEDULED,
            new_status=AppointmentStatus.CONFIRMED,
            previous_notes=None,
            new_notes=None,
            changed_at=now,
        )
        return Page(items=[entry], page=page, page_size=page_size, total=1)


@pytest.fixture
def client() -> TestClient:
    fake_service = FakeAppointmentService()
    app.dependency_overrides[get_appointment_service] = lambda: fake_service
    app.dependency_overrides[get_appointment_history_service] = FakeAppointmentHistoryService
    app.dependency_overrides[get_current_user] = _fake_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_appointment_requires_auth(client: TestClient) -> None:
    del app.dependency_overrides[get_current_user]

    response = client.post(
        "/appointments/",
        json={"customer_id": "customer-1", "scheduled_at": "2026-01-01T10:00:00Z"},
    )

    assert response.status_code == 401


def test_create_appointment_for_known_customer(client: TestClient) -> None:
    response = client.post(
        "/appointments/",
        json={"customer_id": "customer-1", "scheduled_at": "2026-01-01T10:00:00Z"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["created_by_user_id"] == "user-1"


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
    assert updated.json()["updated_by_user_id"] == "user-1"


def test_get_appointment_history(client: TestClient) -> None:
    response = client.get("/appointments/with-history/history")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["new_status"] == "confirmed"


def test_get_appointment_history_not_found(client: TestClient) -> None:
    response = client.get("/appointments/missing/history")

    assert response.status_code == 404
