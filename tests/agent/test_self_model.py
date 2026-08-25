from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from noosfera_core.agent.cognition import CognitiveCycleStore
from noosfera_core.agent.cognition_api import create_cognition_app
from noosfera_core.agent.self_model import RegistrySelfModel, grounded_self_response
from noosfera_core.config import Settings
from noosfera_core.manifest import load_service_manifest

ROOT = Path(__file__).resolve().parents[2]
COGNITION_MANIFEST = ROOT / "services/cognition-service/service.yaml"


@pytest.mark.asyncio
async def test_self_model_keeps_declared_observed_and_verified_separate() -> None:
    manifest = load_service_manifest(COGNITION_MANIFEST)
    model = RegistrySelfModel(
        registry_path=ROOT / "registry",
        node_id="node-self-model-test",
        current_manifest=manifest,
        cache_seconds=0,
    )
    snapshot = await model.snapshot(force_refresh=True)

    provided = {
        module_id for provider in manifest.providers for module_id in provider.modules
    }
    assert set(snapshot.observed_modules) == provided
    assert "COG-12" in snapshot.declared_modules
    assert "COG-12" in snapshot.observed_modules
    assert "COG-12" in snapshot.observed_not_verified
    assert set(snapshot.verified_modules).issubset(snapshot.observed_modules)
    assert set(snapshot.observed_modules).issubset(snapshot.declared_modules)
    assert snapshot.declared_not_observed
    assert snapshot.internal_state.affective_state == "sealed-unobserved"
    assert snapshot.internal_state.claim_policy == "must-not-fabricate"


@pytest.mark.asyncio
async def test_snapshot_hash_is_stable_across_collection_times() -> None:
    manifest = load_service_manifest(COGNITION_MANIFEST)
    model = RegistrySelfModel(
        registry_path=ROOT / "registry",
        node_id="node-stable-hash-test",
        current_manifest=manifest,
        cache_seconds=0,
    )
    first = await model.snapshot(force_refresh=True)
    second = await model.snapshot(force_refresh=True)
    assert first.generated_at <= second.generated_at
    assert first.snapshot_hash == second.snapshot_hash


@pytest.mark.asyncio
async def test_user_affect_does_not_become_sheily_internal_state() -> None:
    manifest = load_service_manifest(COGNITION_MANIFEST)
    model = RegistrySelfModel(
        registry_path=ROOT / "registry",
        node_id="node-affect-isolation-test",
        current_manifest=manifest,
    )
    snapshot = await model.snapshot()

    assert grounded_self_response("Estoy triste, ayúdame", snapshot) is None
    response = grounded_self_response("¿Qué sientes internamente?", snapshot)
    assert response is not None
    assert response.internal_state_claims == []
    assert response.system_evidence[0].evidence_hash == snapshot.snapshot_hash
    assert "No dispongo de evidencia verificable" in response.answer
    assert "no debo inventar" in response.answer


def test_cognition_self_model_endpoint_requires_service_identity() -> None:
    settings = Settings(
        self_model_registry_path=str(ROOT / "registry"),
        runtime_registry_urls="",
        internal_service_token="self-model-test-token",  # noqa: S106
    )
    app = create_cognition_app(
        COGNITION_MANIFEST,
        settings=settings,
        store=CognitiveCycleStore(None),
    )

    with TestClient(app) as client:
        assert client.get("/v1/self-model").status_code == 401
        response = client.get(
            "/v1/self-model",
            headers={"X-Noosfera-Service-Token": "self-model-test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "noosfera.self-model.v1"
    assert "COG-12" in payload["observed_modules"]
    assert len(payload["snapshot_hash"]) == 64
