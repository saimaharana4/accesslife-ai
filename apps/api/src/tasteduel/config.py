"""Explicit local foundation configuration. No legacy .env or cloud lookup."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def validate_local_url(value: str, *, migration: bool = False) -> str:
    try:
        url = make_url(value)
        valid = (
            url.drivername == "postgresql+psycopg"
            and url.host in {"127.0.0.1", "localhost", "::1"}
            and url.port == 55435
            and url.database == "tasteduel_prompt5"
            and url.username == ("tasteduel_migrator" if migration else "tasteduel_runtime")
        )
    except Exception:
        valid = False
    if not valid:
        raise ValueError("Only the dedicated local Taste Duel foundation database/role is allowed.")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TASTEDUEL_", env_file=None, extra="ignore")
    database_url: SecretStr | None = None
    cookie_secure: bool = True
    cookie_name: str = "tasteduel_session"
    session_ttl_seconds: int = 86400
    allowed_origins: tuple[str, ...] = ("http://127.0.0.1:3001", "http://localhost:3001")
