from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "Otica Lab API"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


class Settings(BaseSettings):
    supabase_url: str = "http://localhost:8000"
    supabase_key: str = "change-me"
    secret_key: str = "change-me-secret-key-at-least-32-chars-long"
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # fields load from env, not the constructor
