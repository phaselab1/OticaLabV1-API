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


class FakeCustomerService:
    def __init__(self) -> None:
        self.rows: dict[str, Customer] = {}

    async def create(self, data: CustomerCreate) -> Customer:
        now = datetime.now(UTC)
        customer = Customer(
            id=str(len(self.rows) + 1),
            full_name=data.full_name,
            date_of_birth=data.date_of_birth,
            phone=data.phone,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.rows[customer.id] = customer
        return customer

    async def get_all(self, *, page: int, page_size: int) -> Page[Customer]:
        items = list(self.rows.values())
        return Page(items=items, page=page, page_size=page_size, total=len(items))

    async def get_by_id(self, customer_id: str) -> Customer:
        customer = self.rows.get(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    async def update(self, customer_id: str, data: CustomerUpdate) -> Customer:
        customer = await self.get_by_id(customer_id)
        updated = replace(customer, **data.model_dump(exclude_unset=True))
        self.rows[customer_id] = updated
        return updated

    async def delete(self, customer_id: str) -> None:
        await self.get_by_id(customer_id)
        del self.rows[customer_id]


@pytest.fixture
def client() -> TestClient:
    fake_service = FakeCustomerService()
    app.dependency_overrides[get_customer_service] = lambda: fake_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_customer(client: TestClient) -> None:
    response = client.post(
        "/customers/", json={"full_name": "Ana Silva", "date_of_birth": "1990-01-01"}
    )

    assert response.status_code == 201
    assert response.json()["full_name"] == "Ana Silva"


def test_get_customer_not_found(client: TestClient) -> None:
    response = client.get("/customers/missing")

    assert response.status_code == 404


def test_full_crud_flow(client: TestClient) -> None:
    created = client.post(
        "/customers/", json={"full_name": "Bruno Souza", "date_of_birth": "1985-05-05"}
    ).json()
    customer_id = created["id"]

    got = client.get(f"/customers/{customer_id}")
    assert got.status_code == 200

    updated = client.put(f"/customers/{customer_id}", json={"phone": "11999999999"})
    assert updated.status_code == 200
    assert updated.json()["phone"] == "11999999999"

    deleted = client.delete(f"/customers/{customer_id}")
    assert deleted.status_code == 204

    after_delete = client.get(f"/customers/{customer_id}")
    assert after_delete.status_code == 404
