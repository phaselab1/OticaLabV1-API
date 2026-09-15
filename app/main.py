from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.appointments.exceptions import register_appointment_exception_handlers
from app.appointments.router import router as appointments_router
from app.auth.exceptions import register_auth_exception_handlers
from app.auth.router import router as auth_router
from app.core.config import APP_NAME, get_settings
from app.core.database import close_supabase
from app.core.exceptions import register_exception_handlers
from app.customers.exceptions import register_customer_exception_handlers
from app.customers.router import router as customers_router
from app.users.exceptions import register_user_exception_handlers
from app.users.router import router as users_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await close_supabase()


app = FastAPI(title=APP_NAME, debug=settings.debug, lifespan=lifespan)

register_exception_handlers(app)
register_customer_exception_handlers(app)
register_appointment_exception_handlers(app)
register_user_exception_handlers(app)
register_auth_exception_handlers(app)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(customers_router)
app.include_router(appointments_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
