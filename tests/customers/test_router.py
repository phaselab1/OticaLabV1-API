from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.customers.dependencies import get_customer_service
from app.customers.exceptions import CustomerNotFoundError
from app.customers.model import Customer
from app.customers.schema import CustomerCreate, CustomerUpdate
from app.main import app
from app.shared.pagination import Page
from app.users.dependencies import get_current_user
from app.users.model import User, UserRole

VALID_PHONE = "11999999999"


def _fake_user() -> User:
    now = datetime.now(UTC)
    return User(
        id="user-1",
        full_name="Admin",
        email="admin@example.com",
        password_hash="hash",
        role=UserRole.SUPER_ADMIN,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


class FakeCustomerService:
    def __init__(self) -> None:
        self.rows: dict[str, Customer] = {}

    async def create(self, data: CustomerCreate, current_user: User) -> Customer:
        now = datetime.now(UTC)
        customer = Customer(
            id=str(len(self.rows) + 1),
            company_id=data.company_id or "company-a",
            company_unit_id=data.company_unit_id or "unit-a1",
            full_name=data.full_name,
            date_of_birth=data.date_of_birth,
            phone=data.phone,
            created_by_user_id=current_user.id,
            updated_by_user_id=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.rows[customer.id] = customer
        return customer

    async def get_all(self, **_: object) -> Page[Customer]:
        items = list(self.rows.values())
        return Page(items=items, page=1, page_size=20, total=len(items))

    async def get_by_id(self, customer_id: str) -> Customer:
        customer = self.rows.get(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    async def update(self, customer_id: str, data: CustomerUpdate, current_user: User) -> Customer:
        customer = await self.get_by_id(customer_id)
        updated = replace(
            customer, updated_by_user_id=current_user.id, **data.model_dump(exclude_unset=True)
        )
        self.rows[customer_id] = updated
        return updated

    async def delete(self, customer_id: str) -> None:
        await self.get_by_id(customer_id)
        del self.rows[customer_id]


@pytest.fixture
def client() -> TestClient:
    fake_service = FakeCustomerService()
    app.dependency_overrides[get_customer_service] = lambda: fake_service
    app.dependency_overrides[get_current_user] = _fake_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_customer_requires_auth(client: TestClient) -> None:
    del app.dependency_overrides[get_current_user]

    response = client.post(
        "/customers/",
        json={
            "full_name": "Ana Silva",
            "date_of_birth": "1990-01-01",
            "company_id": "company-a",
            "company_unit_id": "unit-a1",
        },
    )

    assert response.status_code == 401


def test_create_customer(client: TestClient) -> None:
    response = client.post(
        "/customers/",
        json={
            "full_name": "Ana Silva",
            "date_of_birth": "1990-01-01",
            "company_id": "company-a",
            "company_unit_id": "unit-a1",
        },
    )

    assert response.status_code == 201
    assert response.json()["full_name"] == "Ana Silva"
    assert response.json()["created_by_user_id"] == "user-1"


def test_create_customer_invalid_phone_rejected(client: TestClient) -> None:
    response = client.post(
        "/customers/",
        json={
            "full_name": "Ana Silva",
            "date_of_birth": "1990-01-01",
            "company_id": "company-a",
            "company_unit_id": "unit-a1",
            "phone": "123",
        },
    )

    assert response.status_code == 422


def test_get_customer_not_found(client: TestClient) -> None:
    response = client.get("/customers/missing")

    assert response.status_code == 404


def test_full_crud_flow(client: TestClient) -> None:
    created = client.post(
        "/customers/",
        json={
            "full_name": "Bruno Souza",
            "date_of_birth": "1985-05-05",
            "company_id": "company-a",
            "company_unit_id": "unit-a1",
        },
    ).json()
    customer_id = created["id"]

    got = client.get(f"/customers/{customer_id}")
    assert got.status_code == 200

    updated = client.put(f"/customers/{customer_id}", json={"phone": VALID_PHONE})
    assert updated.status_code == 200
    assert updated.json()["phone"] == VALID_PHONE
    assert updated.json()["updated_by_user_id"] == "user-1"

    deleted = client.delete(f"/customers/{customer_id}")
    assert deleted.status_code == 204

    after_delete = client.get(f"/customers/{customer_id}")
    assert after_delete.status_code == 404
