from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Single connection for source data AND product.* tables.
    # Required — set DATABASE_URL in the environment or .env file.
    database_url: str

    redis_url: str = ""  # empty → in-memory fallback

    contact_email: str = "vinicius@ambern.dev"
    api_env: str = "development"
    cors_origins: str = "https://brazil.ambern.dev,http://localhost:3100"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
