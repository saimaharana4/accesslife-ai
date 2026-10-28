"""Pinned database secret resolution, server ADC only; never log payloads."""

import os
from urllib.parse import urlsplit

from tasteduel.config import Settings, validate_database_url


class DatabaseConfigurationError(RuntimeError):
    pass


def _read(reference: str) -> str:
    from google.cloud import secretmanager

    with secretmanager.SecretManagerServiceClient() as client:
        response = client.access_secret_version(request={"name": reference}, retry=None, timeout=5)
        value = response.payload.data.decode("utf-8")
    if not 32 <= len(value) <= 4096 or any(character in value for character in "\r\n\x00"):
        raise DatabaseConfigurationError("Database secret format is invalid.")
    return value


def resolve_database_url(settings: Settings, *, migration: bool = False, reader=None) -> str:
    """Resolve the allowlisted role-specific reference, not arbitrary secret IDs."""
    try:
        if settings.database_mode == "local":
            value = os.environ.get("TASTEDUEL_MIGRATION_DATABASE_URL", "") if migration else (
                settings.database_url.get_secret_value() if settings.database_url else ""
            )
        else:
            # A configured raw URL must never silently override the reviewed ref.
            if settings.database_url is not None or os.environ.get("TASTEDUEL_MIGRATION_DATABASE_URL"):
                raise DatabaseConfigurationError("Direct database URLs are disabled in cloud mode.")
            reference = settings.migration_database_secret_version if migration else settings.database_secret_version
            if reference is None:
                raise DatabaseConfigurationError("A pinned database secret reference is required.")
            if settings.qloo_enabled and settings.qloo_secret_version.endswith("/latest"):
                raise DatabaseConfigurationError("Cloud provider secrets require pinned numeric versions.")
            if not migration:
                if not settings.cookie_secure or settings.vertex_project != "project-bb13ecd8-9d67-408d-9a7":
                    raise DatabaseConfigurationError("Cloud identity/cookie configuration is invalid.")
                if settings.vertex_requests_per_day > 50 or settings.vertex_tokens_per_day > 500_000:
                    raise DatabaseConfigurationError("Cloud model admission exceeds the reviewed release envelope.")
                origins = [urlsplit(origin) for origin in settings.allowed_origins]
                if not origins or any(origin.scheme != "https" or not origin.hostname or origin.username
                                      or origin.password or origin.port is not None
                                      or origin.path or origin.query or origin.fragment for origin in origins):
                    raise DatabaseConfigurationError("Cloud mutation origins require exact HTTPS origins.")
            value = (reader or _read)(reference)
        return validate_database_url(value, mode=settings.database_mode, migration=migration,
                                     connection_name=settings.cloud_sql_connection_name)
    except DatabaseConfigurationError:
        raise
    except Exception:
        raise DatabaseConfigurationError("Taste Duel database configuration is unavailable or invalid.") from None
