from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "CORE API"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://core_user:core_password@localhost:5433/core_db"
    # Alembic: Supabase direct or session-pooler (5432). Falls back to database_url.
    database_url_migrations: str | None = None
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
