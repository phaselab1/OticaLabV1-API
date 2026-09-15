from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

PHONE_PATTERN = r"^\d{10,11}$"


class CustomerCreate(BaseModel):
    full_name: str = Field(description="Nome completo do cliente.", examples=["Bruno Souza"])
    date_of_birth: date = Field(description="Data de nascimento.", examples=["1990-05-20"])
    phone: str | None = Field(
        default=None,
        pattern=PHONE_PATTERN,
        description="Telefone com DDD, só dígitos (10 ou 11 caracteres), sem máscara. Não é único.",
        examples=["11987654321"],
    )
    company_id: str | None = Field(
        default=None,
        description=(
            "UUID da empresa. Obrigatório para `super_admin`; para os demais roles, "
            "preenchido automaticamente a partir do vínculo em `company_users` quando omitido "
            "(erro 400 se o usuário tiver acesso a mais de uma empresa e não especificar)."
        ),
    )
    company_unit_id: str | None = Field(
        default=None,
        description=(
            "UUID da unidade. Obrigatório para `super_admin` e para `admin`; para `manager`/"
            "`attendant` vinculados a exatamente uma unidade, preenchido automaticamente quando "
            "omitido (erro 400 se houver ambiguidade)."
        ),
    )


class CustomerUpdate(BaseModel):
    full_name: str | None = Field(default=None, description="Novo nome, se for alterar.")
    date_of_birth: date | None = Field(
        default=None, description="Nova data de nascimento, se for alterar."
    )
    phone: str | None = Field(
        default=None, pattern=PHONE_PATTERN, description="Novo telefone, se for alterar."
    )


class CustomerResponse(BaseModel):
    id: str = Field(description="UUID do cliente.")
    company_id: str
    company_unit_id: str = Field(
        description="Unidade de cadastro — também a unidade de todos os agendamentos deste cliente."
    )
    full_name: str
    date_of_birth: date
    phone: str | None
    created_by_user_id: str = Field(description="UUID de quem cadastrou o cliente. Nunca muda.")
    updated_by_user_id: str | None = Field(
        description="UUID de quem fez a última alteração. Nulo até a primeira edição."
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
