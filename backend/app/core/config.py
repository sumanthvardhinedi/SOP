from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded strictly from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "Multi-Shop Sales Data API"
    API_V1_PREFIX: str = "/api/v1"

    # Database configuration (PostgreSQL + asyncpg)
    DATABASE_URL: str = Field(
        ...,
        description="Async SQLAlchemy PostgreSQL connection URL (postgresql+asyncpg://...)",
    )

    # JWT configuration (used starting in Phase 2)
    JWT_SECRET_KEY: str = Field(
        ...,
        min_length=16,
        description="Secret key used to sign JWT access tokens",
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, gt=0)

    # Upload limits (used starting in Phase 3)
    MAX_UPLOAD_SIZE_MB: int = Field(default=20, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()


settings = get_settings()
