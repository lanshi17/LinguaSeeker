from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/acmg_lingua"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"

    # Security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30

    # App
    debug: bool = False
    api_v1_prefix: str = "/api/v1"


settings = Settings()
