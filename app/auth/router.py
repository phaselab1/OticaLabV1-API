from fastapi import APIRouter

from app.auth.dependencies import AuthServiceDep
from app.auth.schema import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    token = await service.login(data.email, data.password)
    return TokenResponse(access_token=token)
