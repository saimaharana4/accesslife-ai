"""Resolve explicitly configured Secret Manager references with ADC; never log payloads."""

from functools import lru_cache
from google.cloud import secretmanager
from accesslife.config import settings
from accesslife.ports.providers import ProviderError


@lru_cache(maxsize=20)
def read_secret(resource: str) -> str:
    if not resource.startswith("projects/") or "/secrets/" not in resource:
        raise ProviderError("invalid_secret_reference")
    if "/versions/" not in resource:
        resource += "/versions/latest"
    try:
        response = secretmanager.SecretManagerServiceClient().access_secret_version(
            request={"name": resource}, timeout=5
        )
        return response.payload.data.decode("utf-8").strip()
    except Exception:
        raise ProviderError("secret_unavailable") from None


def credential(name: str) -> str:
    cfg = settings()
    reference = getattr(cfg, name + "_secret", "")
    return read_secret(reference) if reference else getattr(cfg, name, "")
