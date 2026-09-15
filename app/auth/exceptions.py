from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class InvalidCredentialsError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


def register_auth_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(
        request: Request, exc: InvalidCredentialsError
    ) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})
