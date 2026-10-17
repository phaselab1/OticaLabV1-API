from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.users.model import UserRole


class UserCreate(BaseModel):
    full_name: str = Field(
        max_length=255, description="Nome completo do usuário.", examples=["Ana Silva"]
    )
    email: EmailStr = Field(
        max_length=255, description="E-mail único — vira o login.", examples=["ana@oticalab.com"]
    )
    password: str = Field(
        min_length=8,
        max_length=72,
        description=(
            "Senha em texto plano (8 a 72 caracteres — limite do bcrypt) — "
            "nunca armazenada como tal."
        ),
    )
    role: UserRole = Field(
        default=UserRole.ATTENDANT,
        description=(
            "Papel do usuário. `super_admin` tem acesso global; `admin` acessa uma "
            "empresa inteira; `manager` gerencia uma unidade específica; `attendant` "
            "opera na empresa/unidade(s) às quais foi vinculado via `company_users`."
        ),
    )


class UserUpdate(BaseModel):
    full_name: str | None = Field(
        default=None, max_length=255, description="Novo nome completo, se for alterar."
    )
    email: EmailStr | None = Field(
        default=None, max_length=255, description="Novo e-mail, se for alterar."
    )
    role: UserRole | None = Field(default=None, description="Novo papel, se for alterar.")


class UserResponse(BaseModel):
    id: str = Field(description="UUID do usuário.")
    full_name: str
    email: str
    role: UserRole
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
