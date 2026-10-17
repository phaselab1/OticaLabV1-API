from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.companies.dependencies import get_company_service
from app.companies.model import Company
from app.companies.schema import CompanyCreate
from app.main import app
from app.shared.pagination import Page
from app.users.dependencies import get_current_user
from app.users.model import User, UserRole


class FakeCompanyService:
    def __init__(self) -> None:
        self.rows: dict[str, Company] = {}

    async def create(self, data: CompanyCreate, current_user: User) -> Company:
        now = datetime.now(UTC)
        company = Company(
            id=str(len(self.rows) + 1),
            name=data.name,
            cnpj=data.cnpj,
            state=data.state,
            city=data.city,
            created_by_user_id=current_user.id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.rows[company.id] = company
        return company

    async def get_all(self, current_user: User, **_: object) -> Page[Company]:
        items = list(self.rows.values())
        return Page(items=items, page=1, page_size=20, total=len(items))


def _user(role: UserRole) -> User:
    now = datetime.now(UTC)
    return User(
        id="user-1",
        full_name="Test User",
        email="user@example.com",
        password_hash="hash",
        role=role,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


@pytest.fixture
def fake_service() -> FakeCompanyService:
    return FakeCompanyService()


def _client(fake_service: FakeCompanyService, role: UserRole) -> TestClient:
    app.dependency_overrides[get_company_service] = lambda: fake_service
    app.dependency_overrides[get_current_user] = lambda: _user(role)
    return TestClient(app)


def test_create_company_as_attendant_forbidden(fake_service: FakeCompanyService) -> None:
    with _client(fake_service, UserRole.ATTENDANT) as client:
        response = client.post(
            "/companies/",
            json={"name": "Nova Visao", "cnpj": "12345678000199", "state": "SP", "city": "SP"},
        )
        assert response.status_code == 403
    app.dependency_overrides.clear()


def test_create_company_as_admin_forbidden(fake_service: FakeCompanyService) -> None:
    with _client(fake_service, UserRole.ADMIN) as client:
        response = client.post(
            "/companies/",
            json={"name": "Nova Visao", "cnpj": "12345678000199", "state": "SP", "city": "SP"},
        )
        assert response.status_code == 403
    app.dependency_overrides.clear()


def test_create_company_as_super_admin_succeeds(fake_service: FakeCompanyService) -> None:
    with _client(fake_service, UserRole.SUPER_ADMIN) as client:
        response = client.post(
            "/companies/",
            json={"name": "Nova Visao", "cnpj": "12345678000199", "state": "sp", "city": "SP"},
        )
        assert response.status_code == 201
        assert response.json()["state"] == "SP"
    app.dependency_overrides.clear()


def test_create_company_invalid_cnpj_rejected(fake_service: FakeCompanyService) -> None:
    with _client(fake_service, UserRole.SUPER_ADMIN) as client:
        response = client.post(
            "/companies/",
            json={"name": "Nova Visao", "cnpj": "123", "state": "SP", "city": "SP"},
        )
        assert response.status_code == 422
    app.dependency_overrides.clear()


def test_create_company_invalid_state_rejected(fake_service: FakeCompanyService) -> None:
    with _client(fake_service, UserRole.SUPER_ADMIN) as client:
        response = client.post(
            "/companies/",
            json={"name": "Nova Visao", "cnpj": "12345678000199", "state": "ZZ", "city": "SP"},
        )
        assert response.status_code == 422
    app.dependency_overrides.clear()
