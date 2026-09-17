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


BrazilianState = Annotated[
    str,
    AfterValidator(_validate_state),
    Field(description="UF brasileira (2 letras).", examples=["SP"]),
]


class CompanyCreate(BaseModel):
    name: str = Field(max_length=255, description="Nome da empresa.", examples=["Ótica Nova Visão"])
    cnpj: str = Field(
        pattern=CNPJ_PATTERN,
        description="CNPJ com 14 dígitos numéricos, sem máscara. Só o formato é validado.",
        examples=["12345678000199"],
    )
    state: BrazilianState
    city: str = Field(
        max_length=255, description="Cidade da sede da empresa.", examples=["São Paulo"]
    )


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255, description="Novo nome, se for alterar.")
    cnpj: str | None = Field(
        default=None, pattern=CNPJ_PATTERN, description="Novo CNPJ, se for alterar."
    )
    state: BrazilianState | None = None
    city: str | None = Field(
        default=None, max_length=255, description="Nova cidade, se for alterar."
    )


class CompanyResponse(BaseModel):
    id: str = Field(description="UUID da empresa.")
    name: str
    cnpj: str
    state: str
    city: str
    created_by_user_id: str = Field(description="UUID do super_admin que criou a empresa.")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyUnitCreate(BaseModel):
    name: str = Field(
        max_length=255, description="Nome da unidade.", examples=["Unidade Argentina"]
    )
    code: str = Field(
        max_length=10,
        description="Identificador curto usado no dia a dia (único por empresa).",
        examples=["ARG"],
    )
    cnpj: str = Field(
        pattern=CNPJ_PATTERN,
        description="CNPJ próprio da unidade (padrão matriz/filial), 14 dígitos numéricos.",
        examples=["12345678000280"],
    )
    state: BrazilianState
    city: str = Field(max_length=255, description="Cidade da unidade.", examples=["São Paulo"])


class CompanyUnitUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255, description="Novo nome, se for alterar.")
    code: str | None = Field(
        default=None, max_length=10, description="Novo código, se for alterar."
    )
    cnpj: str | None = Field(
        default=None, pattern=CNPJ_PATTERN, description="Novo CNPJ, se for alterar."
    )
    state: BrazilianState | None = None
    city: str | None = Field(
        default=None, max_length=255, description="Nova cidade, se for alterar."
    )


class CompanyUnitResponse(BaseModel):
    id: str = Field(description="UUID da unidade.")
    company_id: str = Field(description="UUID da empresa à qual esta unidade pertence.")
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
    user_id: str = Field(description="UUID do usuário que vai receber o acesso.")
    unit_id: str | None = Field(
        default=None,
        description=(
            "Omitido/nulo = acesso à empresa inteira (todas as unidades). "
            "Informado = acesso restrito a essa unidade específica. "
            "Usuários com role `manager` são obrigados a informar uma unidade."
        ),
    )


class CompanyUserLinkResponse(BaseModel):
    id: str = Field(description="UUID do vínculo de acesso.")
    company_id: str
    user_id: str
    unit_id: str | None = Field(description="Nulo = acesso à empresa inteira.")
    granted_by_user_id: str = Field(description="UUID de quem concedeu este acesso.")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
