from datetime import UTC, datetime
from typing import Any

import pytest

from app.companies.exceptions import (
    CompanyAlreadyExistsError,
    CompanyNotFoundError,
    CompanyUnitNotFoundError,
    CompanyUserLinkNotFoundError,
    ManagerRequiresUnitError,
)
from app.companies.model import Company, CompanyUnit, CompanyUserLink
from app.companies.schema import CompanyCreate, CompanyUnitCreate, CompanyUserGrant
from app.companies.service import CompanyService, CompanyUnitService, CompanyUserService
from app.core.exceptions import ForbiddenError
from app.users.model import User, UserRole


class FakeCompanyRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def create(self, data: dict[str, Any]) -> Company:
        for row in self.rows.values():
            if row["deleted_at"] is None and row["cnpj"] == data["cnpj"]:
                raise CompanyAlreadyExistsError(data["cnpj"])
        company_id = str(len(self.rows) + 1)
        now = datetime.now(UTC).isoformat()
        row = {"id": company_id, "created_at": now, "updated_at": now, "deleted_at": None, **data}
        self.rows[company_id] = row
        return Company.from_row(row)

    async def get_all(
        self, *, page: int, page_size: int, company_ids: list[str] | None = None
    ) -> tuple[list[Company], int]:
        active = [r for r in self.rows.values() if r["deleted_at"] is None]
        if company_ids is not None:
            active = [r for r in active if r["id"] in company_ids]
        return [Company.from_row(r) for r in active], len(active)

    async def get_by_id(self, company_id: str) -> Company | None:
        row = self.rows.get(company_id)
        if row is None or row["deleted_at"] is not None:
            return None
        return Company.from_row(row)

    async def update(self, company_id: str, data: dict[str, Any]) -> Company | None:
        row = self.rows.get(company_id)
        if row is None or row["deleted_at"] is not None:
            return None
        row.update(data)
        return Company.from_row(row)

    async def soft_delete(self, company_id: str) -> bool:
        row = self.rows.get(company_id)
        if row is None or row["deleted_at"] is not None:
            return False
        row["deleted_at"] = datetime.now(UTC).isoformat()
        return True


class FakeCompanyUnitRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def create(self, data: dict[str, Any]) -> CompanyUnit:
        unit_id = str(len(self.rows) + 1)
        now = datetime.now(UTC).isoformat()
        row = {"id": unit_id, "created_at": now, "updated_at": now, "deleted_at": None, **data}
        self.rows[unit_id] = row
        return CompanyUnit.from_row(row)

    async def get_all(self, company_id: str, **_: object) -> tuple[list[CompanyUnit], int]:
        active = [
            r
            for r in self.rows.values()
            if r["deleted_at"] is None and r["company_id"] == company_id
        ]
        return [CompanyUnit.from_row(r) for r in active], len(active)

    async def get_by_id(self, unit_id: str) -> CompanyUnit | None:
        row = self.rows.get(unit_id)
        if row is None or row["deleted_at"] is not None:
            return None
        return CompanyUnit.from_row(row)

    async def update(self, unit_id: str, data: dict[str, Any]) -> CompanyUnit | None:
        row = self.rows.get(unit_id)
        if row is None or row["deleted_at"] is not None:
            return None
        row.update(data)
        return CompanyUnit.from_row(row)

    async def soft_delete(self, unit_id: str) -> bool:
        row = self.rows.get(unit_id)
        if row is None or row["deleted_at"] is not None:
            return False
        row["deleted_at"] = datetime.now(UTC).isoformat()
        return True


class FakeCompanyUserRepository:
    def __init__(self, links: list[CompanyUserLink] | None = None) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        for link in links or []:
            self.rows[link.id] = {
                "id": link.id,
                "company_id": link.company_id,
                "user_id": link.user_id,
                "unit_id": link.unit_id,
                "granted_by_user_id": link.granted_by_user_id,
                "created_at": link.created_at.isoformat(),
                "updated_at": link.updated_at.isoformat(),
                "deleted_at": None,
            }

    async def create(self, data: dict[str, Any]) -> CompanyUserLink:
        link_id = str(len(self.rows) + 1)
        now = datetime.now(UTC).isoformat()
        row = {"id": link_id, "created_at": now, "updated_at": now, "deleted_at": None, **data}
        self.rows[link_id] = row
        return CompanyUserLink.from_row(row)

    async def get_all_for_company(
        self, company_id: str, **_: object
    ) -> tuple[list[CompanyUserLink], int]:
        active = [
            r
            for r in self.rows.values()
            if r["deleted_at"] is None and r["company_id"] == company_id
        ]
        return [CompanyUserLink.from_row(r) for r in active], len(active)

    async def get_all_for_user(self, user_id: str) -> list[CompanyUserLink]:
        return [
            CompanyUserLink.from_row(r)
            for r in self.rows.values()
            if r["deleted_at"] is None and r["user_id"] == user_id
        ]

    async def get_by_id(self, link_id: str) -> CompanyUserLink | None:
        row = self.rows.get(link_id)
        if row is None or row["deleted_at"] is not None:
            return None
        return CompanyUserLink.from_row(row)

    async def soft_delete(self, link_id: str) -> bool:
        row = self.rows.get(link_id)
        if row is None or row["deleted_at"] is not None:
            return False
        row["deleted_at"] = datetime.now(UTC).isoformat()
        return True


class FakeUserRepository:
    def __init__(self, users: list[User] | None = None) -> None:
        self.users = {u.id: u for u in (users or [])}

    async def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)


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


def _company_user_service(repo: FakeCompanyUserRepository) -> CompanyUserService:
    return CompanyUserService(repo, None, None, None)  # type: ignore[arg-type]


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


async def test_create_company() -> None:
    service = CompanyService(
        FakeCompanyRepository(), _company_user_service(FakeCompanyUserRepository())
    )  # type: ignore[arg-type]
    super_admin = _user(UserRole.SUPER_ADMIN)

    company = await service.create(
        CompanyCreate(name="Nova Visao", cnpj="12345678000199", state="sp", city="Sao Paulo"),
        super_admin,
    )

    assert company.name == "Nova Visao"
    assert company.state == "SP"
    assert company.created_by_user_id == super_admin.id


async def test_create_company_duplicate_cnpj_raises() -> None:
    service = CompanyService(
        FakeCompanyRepository(), _company_user_service(FakeCompanyUserRepository())
    )  # type: ignore[arg-type]
    super_admin = _user(UserRole.SUPER_ADMIN)
    data = CompanyCreate(name="Nova Visao", cnpj="12345678000199", state="SP", city="Sao Paulo")
    await service.create(data, super_admin)

    with pytest.raises(CompanyAlreadyExistsError):
        await service.create(data, super_admin)


async def test_get_by_id_missing_raises_not_found() -> None:
    service = CompanyService(
        FakeCompanyRepository(), _company_user_service(FakeCompanyUserRepository())
    )  # type: ignore[arg-type]
    with pytest.raises(CompanyNotFoundError):
        await service.get_by_id("missing", _user(UserRole.SUPER_ADMIN))


async def test_super_admin_sees_all_companies() -> None:
    repo = FakeCompanyRepository()
    company_user_repo = FakeCompanyUserRepository()
    service = CompanyService(repo, _company_user_service(company_user_repo))  # type: ignore[arg-type]
    super_admin = _user(UserRole.SUPER_ADMIN)
    await service.create(
        CompanyCreate(name="A", cnpj="11111111000100", state="SP", city="X"), super_admin
    )
    await service.create(
        CompanyCreate(name="B", cnpj="22222222000100", state="RJ", city="Y"), super_admin
    )

    page = await service.get_all(super_admin, page=1, page_size=20)

    assert page.total == 2


async def test_admin_sees_only_linked_companies() -> None:
    repo = FakeCompanyRepository()
    super_admin = _user(UserRole.SUPER_ADMIN)
    company_a = await CompanyService(
        repo, _company_user_service(FakeCompanyUserRepository())
    ).create(  # type: ignore[arg-type]
        CompanyCreate(name="A", cnpj="11111111000100", state="SP", city="X"), super_admin
    )
    await CompanyService(repo, _company_user_service(FakeCompanyUserRepository())).create(  # type: ignore[arg-type]
        CompanyCreate(name="B", cnpj="22222222000100", state="RJ", city="Y"), super_admin
    )

    admin = _user(UserRole.ADMIN, user_id="admin-1")
    company_user_repo = FakeCompanyUserRepository([_link(admin.id, company_a.id, None)])
    service = CompanyService(repo, _company_user_service(company_user_repo))  # type: ignore[arg-type]

    page = await service.get_all(admin, page=1, page_size=20)

    assert page.total == 1
    assert page.items[0].id == company_a.id


async def test_create_unit_requires_existing_company() -> None:
    service = CompanyUnitService(
        FakeCompanyUnitRepository(),
        FakeCompanyRepository(),
        _company_user_service(FakeCompanyUserRepository()),
    )  # type: ignore[arg-type]
    super_admin = _user(UserRole.SUPER_ADMIN)

    with pytest.raises(CompanyNotFoundError):
        await service.create(
            "missing",
            CompanyUnitCreate(name="ARG", code="ARG", cnpj="11111111000200", state="SP", city="X"),
            super_admin,
        )


async def test_grant_access_requires_company_admin_access() -> None:
    company_repo = FakeCompanyRepository()
    super_admin = _user(UserRole.SUPER_ADMIN)
    company = await CompanyService(
        company_repo, _company_user_service(FakeCompanyUserRepository())
    ).create(  # type: ignore[arg-type]
        CompanyCreate(name="A", cnpj="11111111000100", state="SP", city="X"), super_admin
    )

    attendant = _user(UserRole.ATTENDANT, user_id="attendant-1")
    company_user_repo = FakeCompanyUserRepository([_link(attendant.id, company.id, "unit-1")])
    service = CompanyUserService(
        company_user_repo,  # type: ignore[arg-type]
        company_repo,  # type: ignore[arg-type]
        FakeCompanyUnitRepository(),  # type: ignore[arg-type]
        FakeUserRepository([_user(UserRole.ATTENDANT, user_id="new-user")]),  # type: ignore[arg-type]
    )

    with pytest.raises(ForbiddenError):
        await service.grant(company.id, CompanyUserGrant(user_id="new-user"), attendant)


async def test_super_admin_can_grant_access() -> None:
    company_repo = FakeCompanyRepository()
    super_admin = _user(UserRole.SUPER_ADMIN)
    company = await CompanyService(
        company_repo, _company_user_service(FakeCompanyUserRepository())
    ).create(  # type: ignore[arg-type]
        CompanyCreate(name="A", cnpj="11111111000100", state="SP", city="X"), super_admin
    )

    service = CompanyUserService(
        FakeCompanyUserRepository(),  # type: ignore[arg-type]
        company_repo,  # type: ignore[arg-type]
        FakeCompanyUnitRepository(),  # type: ignore[arg-type]
        FakeUserRepository([_user(UserRole.ATTENDANT, user_id="new-user")]),  # type: ignore[arg-type]
    )

    link = await service.grant(company.id, CompanyUserGrant(user_id="new-user"), super_admin)

    assert link.company_id == company.id
    assert link.user_id == "new-user"
    assert link.unit_id is None


async def test_revoke_by_outsider_forbidden() -> None:
    company_repo = FakeCompanyRepository()
    super_admin = _user(UserRole.SUPER_ADMIN)
    company = await CompanyService(
        company_repo, _company_user_service(FakeCompanyUserRepository())
    ).create(  # type: ignore[arg-type]
        CompanyCreate(name="A", cnpj="11111111000100", state="SP", city="X"), super_admin
    )
    grant_repo = FakeCompanyUserRepository()
    grant_service = CompanyUserService(
        grant_repo,  # type: ignore[arg-type]
        company_repo,  # type: ignore[arg-type]
        FakeCompanyUnitRepository(),  # type: ignore[arg-type]
        FakeUserRepository([_user(UserRole.ATTENDANT, user_id="new-user")]),  # type: ignore[arg-type]
    )
    link = await grant_service.grant(company.id, CompanyUserGrant(user_id="new-user"), super_admin)

    outsider = _user(UserRole.ATTENDANT, user_id="outsider-1")
    with pytest.raises(ForbiddenError):
        await grant_service.revoke(link.id, outsider)


async def test_revoke_missing_link_raises_not_found() -> None:
    service = CompanyUserService(
        FakeCompanyUserRepository(),  # type: ignore[arg-type]
        FakeCompanyRepository(),  # type: ignore[arg-type]
        FakeCompanyUnitRepository(),  # type: ignore[arg-type]
        FakeUserRepository(),  # type: ignore[arg-type]
    )
    super_admin = _user(UserRole.SUPER_ADMIN)

    with pytest.raises(CompanyUserLinkNotFoundError):
        await service.revoke("missing", super_admin)


async def test_grant_unknown_unit_raises_not_found() -> None:
    company_repo = FakeCompanyRepository()
    super_admin = _user(UserRole.SUPER_ADMIN)
    company = await CompanyService(
        company_repo, _company_user_service(FakeCompanyUserRepository())
    ).create(  # type: ignore[arg-type]
        CompanyCreate(name="A", cnpj="11111111000100", state="SP", city="X"), super_admin
    )
    service = CompanyUserService(
        FakeCompanyUserRepository(),  # type: ignore[arg-type]
        company_repo,  # type: ignore[arg-type]
        FakeCompanyUnitRepository(),  # type: ignore[arg-type]
        FakeUserRepository([_user(UserRole.ATTENDANT, user_id="new-user")]),  # type: ignore[arg-type]
    )

    with pytest.raises(CompanyUnitNotFoundError):
        await service.grant(
            company.id, CompanyUserGrant(user_id="new-user", unit_id="missing-unit"), super_admin
        )


async def test_grant_manager_without_unit_raises() -> None:
    company_repo = FakeCompanyRepository()
    super_admin = _user(UserRole.SUPER_ADMIN)
    company = await CompanyService(
        company_repo, _company_user_service(FakeCompanyUserRepository())
    ).create(  # type: ignore[arg-type]
        CompanyCreate(name="A", cnpj="11111111000100", state="SP", city="X"), super_admin
    )
    service = CompanyUserService(
        FakeCompanyUserRepository(),  # type: ignore[arg-type]
        company_repo,  # type: ignore[arg-type]
        FakeCompanyUnitRepository(),  # type: ignore[arg-type]
        FakeUserRepository([_user(UserRole.MANAGER, user_id="manager-1")]),  # type: ignore[arg-type]
    )

    with pytest.raises(ManagerRequiresUnitError):
        await service.grant(company.id, CompanyUserGrant(user_id="manager-1"), super_admin)


async def test_grant_manager_with_unit_succeeds() -> None:
    company_repo = FakeCompanyRepository()
    unit_repo = FakeCompanyUnitRepository()
    super_admin = _user(UserRole.SUPER_ADMIN)
    company = await CompanyService(
        company_repo, _company_user_service(FakeCompanyUserRepository())
    ).create(  # type: ignore[arg-type]
        CompanyCreate(name="A", cnpj="11111111000100", state="SP", city="X"), super_admin
    )
    unit = await CompanyUnitService(
        unit_repo, company_repo, _company_user_service(FakeCompanyUserRepository())
    ).create(  # type: ignore[arg-type]
        company.id,
        CompanyUnitCreate(name="ARG", code="ARG", cnpj="11111111000200", state="SP", city="X"),
        super_admin,
    )
    service = CompanyUserService(
        FakeCompanyUserRepository(),  # type: ignore[arg-type]
        company_repo,  # type: ignore[arg-type]
        unit_repo,  # type: ignore[arg-type]
        FakeUserRepository([_user(UserRole.MANAGER, user_id="manager-1")]),  # type: ignore[arg-type]
    )

    link = await service.grant(
        company.id, CompanyUserGrant(user_id="manager-1", unit_id=unit.id), super_admin
    )

    assert link.unit_id == unit.id
