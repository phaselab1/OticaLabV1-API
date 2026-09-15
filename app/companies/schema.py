from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

BRAZILIAN_STATES = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}  # fmt: skip

CNPJ_PATTERN = r"^\d{14}$"


def _validate_state(value: str) -> str:
    normalized = value.upper()
    if normalized not in BRAZILIAN_STATES:
        raise ValueError("invalid Brazilian state code")
    return normalized


BrazilianState = Annotated[str, AfterValidator(_validate_state)]


class CompanyCreate(BaseModel):
    name: str
    cnpj: str = Field(pattern=CNPJ_PATTERN)
    state: BrazilianState
    city: str


class CompanyUpdate(BaseModel):
    name: str | None = None
    cnpj: str | None = Field(default=None, pattern=CNPJ_PATTERN)
    state: BrazilianState | None = None
    city: str | None = None


class CompanyResponse(BaseModel):
    id: str
    name: str
    cnpj: str
    state: str
    city: str
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyUnitCreate(BaseModel):
    name: str
    code: str = Field(max_length=10)
    cnpj: str = Field(pattern=CNPJ_PATTERN)
    state: BrazilianState
    city: str


class CompanyUnitUpdate(BaseModel):
    name: str | None = None
    code: str | None = Field(default=None, max_length=10)
    cnpj: str | None = Field(default=None, pattern=CNPJ_PATTERN)
    state: BrazilianState | None = None
    city: str | None = None


class CompanyUnitResponse(BaseModel):
    id: str
    company_id: str
    name: str
    code: str
    cnpj: str
    state: str
    city: str
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyUserGrant(BaseModel):
    user_id: str
    unit_id: str | None = None


class CompanyUserLinkResponse(BaseModel):
    id: str
    company_id: str
    user_id: str
    unit_id: str | None
    granted_by_user_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
