"""Every address, path and secret the application needs.

Nothing else in the codebase reads os.environ or hard-codes a URL. Moving to
the college server should mean editing .env and nothing else.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    STORAGE_ROOT: str
    MAX_UPLOAD_MB: int = 10
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        # A browser matches the Origin header exactly, so these must be full
        # origins ("http://localhost:5173"), never a bare host or a trailing slash.
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    # Cached so the .env file is read once per process rather than per request.
    return Settings()


settings = get_settings()
