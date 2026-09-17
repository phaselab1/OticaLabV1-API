from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "Otica Lab API"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    secret_key: str
    debug: bool = False
    cors_allowed_origins: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # fields load from env, not the constructor
