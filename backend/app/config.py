"""
Y corp. Ops — Application configuration via environment variables.

Uses pydantic-settings. The app refuses to start in non-dev mode
if SECRET_KEY is still the placeholder.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    api_host: str = "0.0.0.0"  # nosec B104
    api_port: int = 8000
    allowed_origins: str = "http://localhost:5173"

    # Database
    database_url: str = "postgresql://newtonite:newtonite_dev_pass@db:5432/newtonite"

    # Session
    session_expire_hours: int = 8

    # Worker
    worker_poll_interval: int = 2
    worker_batch_size: int = 10
    worker_max_attempts: int = 6
    worker_stuck_timeout_seconds: int = 60

    # Rate limiting
    login_rate_limit_per_minute: int = 10

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    def validate_production(self) -> None:
        """Refuse to start in non-dev mode with placeholder secrets."""
        if not self.is_dev and self.secret_key == "CHANGE-ME-IN-PRODUCTION":
            raise RuntimeError(
                "SECRET_KEY must be changed from the placeholder in non-development mode. "
                "Set a strong random value via the SECRET_KEY environment variable."
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
