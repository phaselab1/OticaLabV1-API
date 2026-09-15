from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from supabase import AsyncClient

from app.core.database import get_supabase
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

SupabaseClient = Annotated[AsyncClient, Depends(get_supabase)]


async def get_token_payload(
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> dict[str, Any]:
    if token is None:
        raise UnauthorizedError("Missing authentication token")

    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedError("Invalid or expired token")

    return payload
