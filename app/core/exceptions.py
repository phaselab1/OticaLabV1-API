import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError

logger = logging.getLogger("app")

# Postgres SQLSTATE for "invalid input syntax" — hit when a path param that's
# supposed to be a UUID (customer_id, appointment_id, ...) isn't one. Every
# repository passes IDs straight through to PostgREST without pre-validating
# the format, so this is reachable from any `/{id}` route.
INVALID_TEXT_REPRESENTATION = "22P02"

# Postgres SQLSTATE for a foreign key violation — hit when a body field that's
# supposed to reference another row (company_id, company_unit_id, ...) is a
# well-formed UUID that just doesn't exist. Same class of issue as above: an
# input-validation failure, not a server error.
FOREIGN_KEY_VIOLATION = "23503"


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

    @app.exception_handler(APIError)
    async def postgrest_api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        if exc.code == INVALID_TEXT_REPRESENTATION:
            return JSONResponse(status_code=404, content={"detail": "Resource not found"})

        if exc.code == FOREIGN_KEY_VIOLATION:
            return JSONResponse(
                status_code=404, content={"detail": "Referenced resource not found"}
            )

        logger.error(
            "Unhandled PostgREST error on %s %s", request.method, request.url.path, exc_info=exc
        )
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
