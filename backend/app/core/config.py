from functools import lru_cache
import json
from typing import Annotated
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Droplet Manager API"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/droger"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_ttl_minutes: int = 1440
    refresh_ttl_days: int = 7

    token_encryption_key: str = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="

    frontend_url: str = "http://localhost:5173"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    admin_email: str | None = None
    admin_password: str | None = None

    resend_api_key: str | None = None
    sender_email: str = "onboarding@resend.dev"

    login_rate_limit_per_minute: int = 10
    forgot_rate_limit_per_hour: int = 6
    resend_verification_rate_limit_per_hour: int = 6

    lockout_threshold: int = 5
    lockout_minutes: int = 15

    secure_cookies: bool = False
    cookie_samesite: str = "lax"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if value is None:
            return ["http://localhost:5173"]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return ["http://localhost:5173"]
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = []
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [part.strip() for part in raw.split(",") if part.strip()]
        return ["http://localhost:5173"]

    @field_validator("admin_email")
    @classmethod
    def normalize_admin_email(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.lower().strip()

    @field_validator("cookie_samesite")
    @classmethod
    def normalize_samesite(cls, value: str) -> str:
        lowered = value.lower().strip()
        if lowered not in {"lax", "strict", "none"}:
            return "lax"
        return lowered


@lru_cache
def get_settings() -> Settings:
    return Settings()
