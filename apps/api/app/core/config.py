from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Env = Literal["dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

JWT_SECRET_MIN_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    env: Env = Field(default="dev")
    log_level: LogLevel = Field(default="INFO")

    database_url: str = Field(...)
    redis_url: str = Field(...)

    redis_cache_ttl: int = Field(default=60)
    redis_genres_ttl: int = Field(default=300)

    jwt_secret: SecretStr = Field(...)
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=1440)

    rb_user_agent: str = Field(...)
    rb_sync_timeout: int = Field(default=30)
    rb_sync_tag_limit: int = Field(default=500)

    health_check_interval: int = Field(default=21600)
    health_check_timeout: int = Field(default=5)
    health_check_max_failures: int = Field(default=3)

    icy_ambient_poll_interval: int = Field(default=60)
    icy_ambient_top_n: int = Field(default=50)
    icy_ondemand_timeout: int = Field(default=300)

    gofestivals_db_url: str = Field(default="")
    gofestivals_cache_ttl: int = Field(default=3600)

    prometheus_enabled: bool = Field(default=False)
    sentry_dsn: str = Field(default="")

    cors_allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def effective_log_level(self) -> LogLevel:
        if self.is_dev and self.log_level == "INFO":
            return "DEBUG"
        return self.log_level

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, v: SecretStr, info: ValidationInfo) -> SecretStr:
        env = info.data.get("env", "dev")
        if env == "dev":
            return v
        raw = v.get_secret_value()
        if len(raw) < JWT_SECRET_MIN_LENGTH:
            msg = (
                f"JWT_SECRET must be at least {JWT_SECRET_MIN_LENGTH} chars "
                f"in {env} (got {len(raw)})"
            )
            raise ValueError(msg)
        forbidden = ("change_me", "dev_secret", "secret", "changeme", "placeholder")
        low = raw.lower()
        if any(token in low for token in forbidden):
            msg = f"JWT_SECRET contains forbidden placeholder in {env}"
            raise ValueError(msg)
        return v

    @field_validator("rb_user_agent")
    @classmethod
    def _validate_rb_user_agent(cls, v: str, info: ValidationInfo) -> str:
        env = info.data.get("env", "dev")
        if env == "prod" and ("example" in v.lower() or "your-domain" in v.lower()):
            msg = "RB_USER_AGENT looks like a placeholder, set a real identifier"
            raise ValueError(msg)
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:
        msg = (
            "Fallo al cargar configuración. Revisa .env. "
            "Variables requeridas: DATABASE_URL, REDIS_URL, JWT_SECRET, RB_USER_AGENT."
        )
        raise RuntimeError(msg) from exc
