from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

PHONE_PATTERN = r"^\d{10,11}$"


class CustomerCreate(BaseModel):
    full_name: str
    date_of_birth: date
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    # Obrigatorio para super_admin; para admin/attendant, preenchido
    # automaticamente a partir do vinculo em company_users quando omitido.
    company_id: str | None = None
    company_unit_id: str | None = None


class CustomerUpdate(BaseModel):
    full_name: str | None = None
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)


class CustomerResponse(BaseModel):
    id: str
    company_id: str
    company_unit_id: str
    full_name: str
    date_of_birth: date
    phone: str | None
    created_by_user_id: str
    updated_by_user_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
