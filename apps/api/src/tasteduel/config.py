"""Explicit local configuration. No legacy .env or import-time cloud lookup."""

from typing import Literal
import os

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def validate_local_url(value: str, *, migration: bool = False) -> str:
    try:
        url = make_url(value)
        expected_user = "tasteduel_migrator" if migration else "tasteduel_runtime"
        local_foundation = (
            url.host in {"127.0.0.1", "localhost", "::1"}
            and url.port in {55435, 55436}
            and url.database == "tasteduel_prompt5"
        )
        compose_database = (
            os.environ.get("TASTEDUEL_CONTAINER_MODE") == "true"
            and url.host == "database"
            and url.port == 5432
            and url.database == "tasteduel_prompt5"
        )
        valid = url.drivername == "postgresql+psycopg" and (local_foundation or compose_database) and url.username == expected_user
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
    qloo_transport: Literal["mcp", "http_ranked"] = "mcp"
    qloo_http_typed_search: bool = False
    generation_enabled: bool = False
    vertex_project: str = "project-bb13ecd8-9d67-408d-9a7"
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
    qloo_requests_per_day: int = Field(default=1000, ge=1, le=10000)
    vertex_requests_per_day: int = Field(default=100, ge=1, le=1000)
    vertex_tokens_per_day: int = Field(default=1_000_000, ge=10512, le=10_000_000)
    guest_reads_per_minute: int = Field(default=240, ge=1, le=600)
    guest_mutations_per_minute: int = Field(default=120, ge=1, le=240)
    guest_searches_per_minute: int = Field(default=12, ge=1, le=30)
    guest_generations_per_ten_minutes: int = Field(default=6, ge=1, le=12)
