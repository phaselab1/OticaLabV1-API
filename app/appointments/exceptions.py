from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppointmentNotFoundError(Exception):
    def __init__(self, appointment_id: str) -> None:
        super().__init__(f"Appointment {appointment_id} not found")


class AppointmentAlreadyExistsError(Exception):
    def __init__(self, customer_id: str, scheduled_at: str) -> None:
        super().__init__(
            f"Customer {customer_id} already has an active appointment at {scheduled_at}"
        )


def register_appointment_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppointmentNotFoundError)
    async def appointment_not_found_handler(
        request: Request, exc: AppointmentNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(AppointmentAlreadyExistsError)
    async def appointment_already_exists_handler(
        request: Request, exc: AppointmentAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})
