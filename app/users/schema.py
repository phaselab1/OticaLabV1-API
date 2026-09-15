from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.users.model import UserRole


class UserCreate(BaseModel):
    full_name: str = Field(description="Nome completo do usuário.", examples=["Ana Silva"])
    email: EmailStr = Field(
        description="E-mail único — vira o login.", examples=["ana@oticalab.com"]
    )
    password: str = Field(
        min_length=8,
        description="Senha em texto plano (mín. 8 caracteres) — nunca armazenada como tal.",
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
    full_name: str | None = Field(default=None, description="Novo nome completo, se for alterar.")
    email: EmailStr | None = Field(default=None, description="Novo e-mail, se for alterar.")
    role: UserRole | None = Field(default=None, description="Novo papel, se for alterar.")


class UserResponse(BaseModel):
    id: str = Field(description="UUID do usuário.")
    full_name: str
    email: str
    role: UserRole
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
