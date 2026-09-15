from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class NotFoundError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


class ForbiddenError(Exception):
    pass


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(request: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})
