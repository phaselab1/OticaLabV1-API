from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.customers.exceptions import CustomerAlreadyExistsError, CustomerNotFoundError
from app.customers.model import Customer
from app.customers.schema import CustomerCreate, CustomerUpdate
from app.customers.service import CustomerService


class FakeCustomerRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def create(self, data: dict[str, Any]) -> Customer:
        for row in self.rows.values():
            if (
                row["deleted_at"] is None
                and row["full_name"] == data["full_name"]
                and row["date_of_birth"] == data["date_of_birth"]
            ):
                raise CustomerAlreadyExistsError(data["full_name"], data["date_of_birth"])

        customer_id = str(len(self.rows) + 1)
        now = datetime.now(UTC).isoformat()
        row = {"id": customer_id, "created_at": now, "updated_at": now, "deleted_at": None, **data}
        self.rows[customer_id] = row
        return Customer.from_row(row)

    async def get_all(self, *, page: int, page_size: int) -> tuple[list[Customer], int]:
        active = [r for r in self.rows.values() if r["deleted_at"] is None]
        start = (page - 1) * page_size
        page_rows = active[start : start + page_size]
        return [Customer.from_row(r) for r in page_rows], len(active)

    async def get_by_id(self, customer_id: str) -> Customer | None:
        row = self.rows.get(customer_id)
        if row is None or row["deleted_at"] is not None:
            return None
        return Customer.from_row(row)

    async def update(self, customer_id: str, data: dict[str, Any]) -> Customer | None:
        row = self.rows.get(customer_id)
        if row is None or row["deleted_at"] is not None:
            return None
        row.update(data)
        return Customer.from_row(row)

    async def soft_delete(self, customer_id: str) -> bool:
        row = self.rows.get(customer_id)
        if row is None or row["deleted_at"] is not None:
            return False
        row["deleted_at"] = datetime.now(UTC).isoformat()
        return True


@pytest.fixture
def service() -> CustomerService:
    return CustomerService(FakeCustomerRepository())  # type: ignore[arg-type]


async def test_create_then_get_by_id(service: CustomerService) -> None:
    created = await service.create(
        CustomerCreate(full_name="Ana Silva", date_of_birth=date(1990, 1, 1))
    )

    fetched = await service.get_by_id(created.id)

    assert fetched.full_name == "Ana Silva"
    assert fetched.date_of_birth == date(1990, 1, 1)


async def test_create_duplicate_raises_already_exists(service: CustomerService) -> None:
    data = CustomerCreate(full_name="Ana Silva", date_of_birth=date(1990, 1, 1))
    await service.create(data)

    with pytest.raises(CustomerAlreadyExistsError):
        await service.create(data)


async def test_get_by_id_missing_raises_not_found(service: CustomerService) -> None:
    with pytest.raises(CustomerNotFoundError):
        await service.get_by_id("missing")


async def test_delete_then_get_by_id_raises_not_found(service: CustomerService) -> None:
    created = await service.create(
        CustomerCreate(full_name="Bruno Souza", date_of_birth=date(1985, 5, 5))
    )

    await service.delete(created.id)

    with pytest.raises(CustomerNotFoundError):
        await service.get_by_id(created.id)


async def test_update_missing_customer_raises_not_found(service: CustomerService) -> None:
    with pytest.raises(CustomerNotFoundError):
        await service.update("missing", CustomerUpdate(full_name="X"))


async def test_delete_missing_customer_raises_not_found(service: CustomerService) -> None:
    with pytest.raises(CustomerNotFoundError):
        await service.delete("missing")
