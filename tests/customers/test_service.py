from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.companies.model import CompanyUserLink
from app.companies.service import CompanyUserService
from app.core.exceptions import ForbiddenError
from app.customers.exceptions import CustomerAlreadyExistsError, CustomerNotFoundError
from app.customers.model import Customer
from app.customers.schema import CustomerCreate, CustomerUpdate
from app.customers.service import CustomerService
from app.users.model import User, UserRole

COMPANY_A = "company-a"
COMPANY_B = "company-b"
UNIT_A1 = "unit-a1"
UNIT_A2 = "unit-a2"


class FakeCustomerRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def create(self, data: dict[str, Any]) -> Customer:
        for row in self.rows.values():
            if (
                row["deleted_at"] is None
                and row["company_id"] == data["company_id"]
                and row["full_name"] == data["full_name"]
                and row["date_of_birth"] == data["date_of_birth"]
            ):
                raise CustomerAlreadyExistsError(data["full_name"], data["date_of_birth"])

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

    async def get_all(self, **_: object) -> tuple[list[Customer], int]:
        active = [r for r in self.rows.values() if r["deleted_at"] is None]
        return [Customer.from_row(r) for r in active], len(active)

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


class FakeCompanyUserRepository:
    def __init__(self, links: list[CompanyUserLink]) -> None:
        self.links = links

    async def get_all_for_user(self, user_id: str) -> list[CompanyUserLink]:
        return [link for link in self.links if link.user_id == user_id]


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


def _user(role: UserRole, user_id: str = "user-1") -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        full_name="Test User",
        email=f"{user_id}@example.com",
        password_hash="hash",
        role=role,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


def _service(company_user_repository: FakeCompanyUserRepository) -> CustomerService:
    company_user_service = CompanyUserService(
        company_user_repository,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
    )
    return CustomerService(FakeCustomerRepository(), company_user_service)  # type: ignore[arg-type]


async def test_super_admin_must_provide_company_and_unit() -> None:
    service = _service(FakeCompanyUserRepository([]))
    user = _user(UserRole.SUPER_ADMIN)

    created = await service.create(
        CustomerCreate(
            full_name="Ana",
            date_of_birth=date(1990, 1, 1),
            company_id=COMPANY_A,
            company_unit_id=UNIT_A1,
        ),
        user,
    )

    assert created.company_id == COMPANY_A
    assert created.company_unit_id == UNIT_A1
    assert created.created_by_user_id == user.id


async def test_super_admin_without_company_or_unit_raises() -> None:
    from app.companies.exceptions import CompanyOrUnitRequiredError

    service = _service(FakeCompanyUserRepository([]))
    user = _user(UserRole.SUPER_ADMIN)

    with pytest.raises(CompanyOrUnitRequiredError):
        await service.create(CustomerCreate(full_name="Ana", date_of_birth=date(1990, 1, 1)), user)


async def test_admin_gets_company_auto_filled_but_must_choose_unit() -> None:
    from app.companies.exceptions import CompanyOrUnitRequiredError

    user = _user(UserRole.ADMIN)
    repo = FakeCompanyUserRepository([_link(user.id, COMPANY_A, None)])
    service = _service(repo)

    with pytest.raises(CompanyOrUnitRequiredError):
        await service.create(CustomerCreate(full_name="Ana", date_of_birth=date(1990, 1, 1)), user)

    created = await service.create(
        CustomerCreate(full_name="Ana", date_of_birth=date(1990, 1, 1), company_unit_id=UNIT_A1),
        user,
    )
    assert created.company_id == COMPANY_A
    assert created.company_unit_id == UNIT_A1


async def test_attendant_with_single_unit_gets_both_auto_filled() -> None:
    user = _user(UserRole.ATTENDANT)
    repo = FakeCompanyUserRepository([_link(user.id, COMPANY_A, UNIT_A1)])
    service = _service(repo)

    created = await service.create(
        CustomerCreate(full_name="Ana", date_of_birth=date(1990, 1, 1)), user
    )

    assert created.company_id == COMPANY_A
    assert created.company_unit_id == UNIT_A1


async def test_attendant_with_multiple_units_must_choose() -> None:
    from app.companies.exceptions import CompanyOrUnitRequiredError

    user = _user(UserRole.ATTENDANT)
    repo = FakeCompanyUserRepository(
        [_link(user.id, COMPANY_A, UNIT_A1), _link(user.id, COMPANY_A, UNIT_A2)]
    )
    service = _service(repo)

    with pytest.raises(CompanyOrUnitRequiredError):
        await service.create(CustomerCreate(full_name="Ana", date_of_birth=date(1990, 1, 1)), user)


async def test_attendant_with_no_access_to_requested_company_forbidden() -> None:
    user = _user(UserRole.ATTENDANT)
    repo = FakeCompanyUserRepository([_link(user.id, COMPANY_A, UNIT_A1)])
    service = _service(repo)

    with pytest.raises(ForbiddenError):
        await service.create(
            CustomerCreate(
                full_name="Ana",
                date_of_birth=date(1990, 1, 1),
                company_id=COMPANY_B,
                company_unit_id="x",
            ),
            user,
        )


async def test_get_by_id_missing_raises_not_found() -> None:
    service = _service(FakeCompanyUserRepository([]))
    with pytest.raises(CustomerNotFoundError):
        await service.get_by_id("missing")


async def test_update_requires_unit_access() -> None:
    creator = _user(UserRole.ATTENDANT)
    repo = FakeCompanyUserRepository([_link(creator.id, COMPANY_A, UNIT_A1)])
    service = _service(repo)

    created = await service.create(
        CustomerCreate(full_name="Ana", date_of_birth=date(1990, 1, 1)), creator
    )

    outsider = _user(UserRole.ATTENDANT, user_id="user-2")
    with pytest.raises(ForbiddenError):
        await service.update(created.id, CustomerUpdate(full_name="Ana Silva"), outsider)
