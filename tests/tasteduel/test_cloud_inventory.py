"""Synthetic metadata contracts; no ADC, cloud network, or credential payloads."""

import importlib.util
import json
from pathlib import Path


def load_inventory():
    path = Path(__file__).resolve().parents[2] / "scripts/tasteduel_cloud_inventory.py"
    spec = importlib.util.spec_from_file_location("tasteduel_cloud_inventory", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    status_code = 200

    def json(self):
        secret = "SYNTHETIC_MUST_NOT_ESCAPE"
        return {
            "name": "owned-metadata", "state": "ENABLED", "password": secret,
            "payload": {"data": secret}, "terminalCondition": {"state": "CONDITION_SUCCEEDED", "message": secret},
            "template": {"containers": [{"image": "registry/image@sha256:synthetic", "env": [{"value": secret}]}]},
            "revisions": [{"name": "owned-revision", "conditions": [{"state": "CONDITION_SUCCEEDED", "message": secret}], "containers": [{"image": "registry/image@sha256:synthetic", "env": [{"value": secret}]}]}],
            "tasks": [{"name": "task-1", "httpRequest": {"headers": {"Authorization": secret}, "body": secret}}],
            "versions": [{"name": "version-1", "state": "ENABLED", "payload": {"data": secret}}],
            "items": [{"name": "logical-db-or-user", "password": secret}],
        }


class FakeSession:
    def __init__(self):
        self.urls = []

    def get(self, url, *, params, timeout):
        self.urls.append(url)
        assert timeout == 25
        return FakeResponse()


def test_inventory_drops_sensitive_fields_and_only_uses_known_metadata_endpoints():
    module = load_inventory()
    inventory = module.Inventory.__new__(module.Inventory)
    inventory.http = FakeSession()
    inventory.requests = 0
    inventory.errors = []
    result = inventory.collect()
    serialized = json.dumps(result)
    assert "SYNTHETIC_MUST_NOT_ESCAPE" not in serialized
    assert result["tasks"]["listed_count"] == 1
    assert result["services"][0]["revisions"][0]["conditions"] == [{"state": "CONDITION_SUCCEEDED"}]
    assert result["secrets"][0]["versions"][0] == {"name": "version-1", "state": "ENABLED"}
    assert inventory.requests == 31
    assert not inventory.errors
    assert all(":access" not in url and "/projects/" in url or "storage.googleapis.com/storage/v1/b/accesslife-" in url for url in inventory.http.urls)
    assert all("pharma" not in url.lower() for url in inventory.http.urls)
    assert all("/accesslife-" in url or "/accesslife/" in url or "/repositories/accesslife" in url for url in inventory.http.urls)


def test_inventory_http_errors_never_copy_response_payload():
    module = load_inventory()

    class ErrorResponse:
        status_code = 403

        def json(self):
            raise AssertionError("Error response payload must not be read")

    class ErrorSession:
        def get(self, *args, **kwargs):
            return ErrorResponse()

    inventory = module.Inventory.__new__(module.Inventory)
    inventory.http = ErrorSession()
    inventory.requests = 0
    inventory.errors = []
    url = "https://secretmanager.googleapis.com/v1/projects/owned/secrets/accesslife-qloo-api-key"
    assert inventory.get(url) == {}
    assert inventory.errors == [{"resource": url, "status": 403}]
