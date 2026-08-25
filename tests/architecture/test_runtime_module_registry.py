import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from noosfera_core.manifest import ServiceManifest
from noosfera_core.module_registry import install_runtime_module_registry


def manifest(*, endpoint: str = "/work") -> ServiceManifest:
    return ServiceManifest.model_validate(
        {
            "id": "dynamic-test-service",
            "family": "TST",
            "version": "1.0.0",
            "runtime": "python",
            "modules": ["TST-01", "TST-02"],
            "providers": [
                {
                    "id": "dynamic.test-provider",
                    "modules": ["TST-01"],
                    "endpoint": endpoint,
                    "methods": ["POST"],
                    "maturity": "implemented",
                    "capabilities": ["test-work"],
                    "evidence": ["tests/architecture/test_runtime_module_registry.py"],
                }
            ],
            "inbound_buses": [],
            "outbound_buses": [],
            "data_stores": [],
            "health": {"liveness": "/health/live", "readiness": "/health/ready"},
            "slo": "test-slo",
            "runbook": "test-runbook",
            "owner": "test-team",
            "deny_by_default": True,
        }
    )


def test_registry_reports_only_a_route_bound_provider_as_invocable() -> None:
    app = FastAPI()

    @app.post("/work")
    async def work() -> dict[str, bool]:
        return {"worked": True}

    install_runtime_module_registry(app, manifest())
    client = TestClient(app)
    payload = client.get("/v1/modules").json()
    assert payload["provided_modules"] == ["TST-01"]
    assert payload["unprovided_modules"] == ["TST-02"]
    assert payload["providers"][0]["status"] == "loaded"
    assert client.get("/v1/modules/TST-01").json()["invocable"] is True
    assert client.get("/v1/modules/TST-02").json()["invocable"] is False


def test_registry_refuses_a_provider_without_a_bound_route() -> None:
    with pytest.raises(RuntimeError, match="unbound route"):
        install_runtime_module_registry(FastAPI(), manifest(endpoint="/missing"))
