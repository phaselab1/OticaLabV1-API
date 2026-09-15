from fastapi import APIRouter

from app.auth.dependencies import AuthServiceDep
from app.auth.schema import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    responses={401: {"description": "E-mail ou senha inválidos."}},
)
async def login(data: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    """
    Autentica um usuário e devolve um token JWT (`Bearer`).

    Não existe auto-registro: o usuário precisa já existir no banco —
    criado por um `super_admin` via `POST /users`, ou o primeiro
    `super_admin` inserido manualmente (veja `db/migrations/README.md`).

    O token expira em 60 minutos e deve ser enviado em
    `Authorization: Bearer <token>` nas rotas protegidas.
    """
    token = await service.login(data.email, data.password)
    return TokenResponse(access_token=token)
