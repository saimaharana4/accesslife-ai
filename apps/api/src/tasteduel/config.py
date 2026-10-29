"""Explicit isolated local/cloud configuration; no import-time credential I/O."""

from typing import Literal
import os

from pydantic import AwareDatetime, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

CLOUD_SQL_CONNECTION = "project-bb13ecd8-9d67-408d-9a7:asia-south1:accesslife-db"
SECRET_PREFIX = "projects/project-bb13ecd8-9d67-408d-9a7/secrets/"


def validate_local_url(value: str, *, migration: bool = False) -> str:
    try:
        url = make_url(value)
        expected_user = "tasteduel_migrator" if migration else "tasteduel_runtime"
        local_foundation = (
            url.host in {"127.0.0.1", "localhost", "::1"}
            and url.port in {55435, 55436}
            and url.database == "tasteduel_local"
        )
        compose_database = (
            os.environ.get("TASTEDUEL_CONTAINER_MODE") == "true"
            and url.host == "database"
            and url.port == 5432
            and url.database == "tasteduel_local"
        )
        valid = url.drivername == "postgresql+psycopg" and (local_foundation or compose_database) and url.username == expected_user and not url.query
    except Exception:
        valid = False
    if not valid:
        raise ValueError("Only the dedicated local Taste Duel foundation database/role is allowed.")
    return value


def validate_database_url(value: str, *, mode: str = "local", migration: bool = False,
                          connection_name: str = CLOUD_SQL_CONNECTION) -> str:
    if mode == "local":
        return validate_local_url(value, migration=migration)
    try:
        url = make_url(value)
        valid = (
            mode == "cloud_sql" and connection_name == CLOUD_SQL_CONNECTION
            and url.drivername == "postgresql+psycopg"
            and url.username == ("tasteduel_migrator" if migration else "tasteduel_runtime")
            and bool(url.password) and url.database == "tasteduel"
            and url.host is None and url.port is None
            and dict(url.query) == {"host": "/cloudsql/" + CLOUD_SQL_CONNECTION}
        )
    except Exception:
        valid = False
    if not valid:
        raise ValueError("Dedicated Taste Duel Cloud SQL connection configuration is invalid.") from None
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TASTEDUEL_", env_file=None, extra="ignore")
    database_url: SecretStr | None = None
    database_mode: Literal["local", "cloud_sql"] = "local"
    cloud_sql_connection_name: Literal[CLOUD_SQL_CONNECTION] = CLOUD_SQL_CONNECTION
    database_secret_version: str | None = Field(
        default=None, pattern=r"^projects/project-bb13ecd8-9d67-408d-9a7/secrets/tasteduel-runtime-database-url/versions/[1-9][0-9]*$",
    )
    migration_database_secret_version: str | None = Field(
        default=None, pattern=r"^projects/project-bb13ecd8-9d67-408d-9a7/secrets/tasteduel-migrate-database-url/versions/[1-9][0-9]*$",
    )
    cookie_secure: bool = True
    cookie_name: str = "tasteduel_session"
    session_ttl_seconds: int = 86400
    # Cloud release sets the reviewed cutoff; local development has no cutoff.
    session_admission_closes_at: AwareDatetime | None = None
    session_hard_closes_at: AwareDatetime | None = None
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
