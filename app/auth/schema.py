from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(
        max_length=255, description="E-mail cadastrado do usuário.", examples=["admin@oticalab.com"]
    )
    password: str = Field(
        max_length=72,
        description="Senha em texto plano — nunca armazenada, só usada para verificação.",
    )


class TokenResponse(BaseModel):
    access_token: str = Field(description="Token JWT — envie em `Authorization: Bearer <token>`.")
    token_type: str = Field(default="bearer", description="Sempre `bearer`.")
