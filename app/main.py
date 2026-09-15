from fastapi import FastAPI

from app.core.config import APP_NAME, get_settings
from app.core.exceptions import register_exception_handlers

settings = get_settings()

app = FastAPI(title=APP_NAME, debug=settings.debug)

register_exception_handlers(app)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
