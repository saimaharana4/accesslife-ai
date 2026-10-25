"""Explicit local foundation configuration. No legacy .env or cloud lookup."""

from pydantic import Field, SecretStr
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
    # Reference only. Payload is fetched through server ADC when explicitly enabled.
    qloo_enabled: bool = False
    qloo_secret_version: str = Field(
        default="projects/project-bb13ecd8-9d67-408d-9a7/secrets/accesslife-qloo-api-key/versions/latest",
        pattern=r"^projects/project-bb13ecd8-9d67-408d-9a7/secrets/accesslife-qloo-api-key/versions/(latest|[1-9][0-9]*)$",
    )
    qloo_runner_path: str = "runtime/qloo/runner.mjs"
    qloo_node_path: str = "node"
    qloo_startup_timeout: float = Field(default=5, gt=0, le=10, allow_inf_nan=False)
    qloo_call_timeout: float = Field(default=12, gt=0, le=15, allow_inf_nan=False)
    qloo_max_restarts: int = Field(default=2, ge=0, le=2)
    qloo_requests_per_minute: int = Field(default=30, ge=1, le=30)
