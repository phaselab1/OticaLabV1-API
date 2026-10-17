from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class CustomerNotFoundError(Exception):
    def __init__(self, customer_id: str) -> None:
        super().__init__(f"Customer {customer_id} not found")


class CustomerAlreadyExistsError(Exception):
    def __init__(self, full_name: str) -> None:
        super().__init__(f"Customer '{full_name}' already exists")


def register_customer_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CustomerNotFoundError)
    async def customer_not_found_handler(
        request: Request, exc: CustomerNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(CustomerAlreadyExistsError)
    async def customer_already_exists_handler(
        request: Request, exc: CustomerAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})
