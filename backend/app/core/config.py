from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "CORE API"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    # Default = Docker local de docker-compose.yml (credenciales de desarrollo, no secretas).
    # Fuera de local se define siempre por entorno / backend/.env.
    database_url: str = "postgresql+psycopg://core_user:core_password@localhost:5433/core_db"
    # Alembic: Supabase direct or session-pooler (5432). Falls back to database_url.
    database_url_migrations: str | None = None
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3011",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3011",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
