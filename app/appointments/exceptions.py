from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppointmentNotFoundError(Exception):
    def __init__(self, appointment_id: str) -> None:
        super().__init__(f"Appointment {appointment_id} not found")


def register_appointment_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppointmentNotFoundError)
    async def appointment_not_found_handler(
        request: Request, exc: AppointmentNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
