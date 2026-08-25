"""Recorrido vertical de la API con dobles locales explícitos."""

from pathlib import Path

from fastapi.testclient import TestClient
from noosfera_core.agent.api import AgentContainer, create_agent_app
from noosfera_core.agent.models import MissionStatus
from noosfera_core.config import Settings
from noosfera_core.manifest import load_service_manifest

MANIFEST = Path("services/experience-service/service.yaml")


def local_test_settings() -> Settings:
    return Settings(
        storage_backend="memory",
        event_backend="disabled-test",
        identity_backend="in-process-test",
        cognition_backend="in-process-test",
        agency_backend="in-process-test",
        governance_backend="deterministic-test",
        execution_backend="in-process-test",
        model_provider="deterministic",
        local_username="owner",
        local_password="correct-horse-battery-staple",  # noqa: S106 -- test credential
        identity_private_key_b64="fECcWuqB0rjSdD2t6ADoVCOkG6Or8bG/mHeytU39bHs=",  # noqa: S106
        agency_private_key_b64="hM6ZIQvpEOSkYUgaFeJu3u2cNil7rZXxyZsl9a72gqk=",  # noqa: S106
        governance_private_key_b64="x3lPBPxt4rySiYr6hfnQpQborcN/7OcjVr+2qEuqiFQ=",  # noqa: S106
        audit_private_key_b64="TT1KteJqMjx2lLLp70hZcnMKz5P0ypFdNfZ91v88S4g=",  # noqa: S106
        document_verification_backend="in-process-test",
    )


def client_and_headers() -> tuple[TestClient, dict[str, str]]:
    settings = local_test_settings()
    manifest = load_service_manifest(MANIFEST)
    container = AgentContainer.build(settings, manifest)
    client = TestClient(create_agent_app(MANIFEST, settings=settings, container=container))
    login = client.post(
        "/v1/auth/login",
        json={"username": "owner", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200
    return client, {"Authorization": f"Bearer {login.json()['access_token']}"}


def assert_receipt_chain(entries: list[dict[str, object]]) -> None:
    ordered = sorted(entries, key=lambda entry: int(entry["sequence"]))
    previous = "0" * 64
    for entry in ordered:
        assert entry["previous_receipt_hash"] == previous
        previous = str(entry["receipt_hash"])


def test_document_report_requires_approval_then_completes_with_memory_and_audit() -> None:
    client, headers = client_and_headers()
    with client:
        conversation = client.post(
            "/v1/conversations", json={"title": "Informe local"}, headers=headers
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]

        upload = client.post(
            "/v1/documents",
            files={
                "upload": (
                    "evidence.md",
                    b"Sheily procesa esta evidencia local.",
                    "text/markdown",
                )
            },
            headers=headers,
        )
        assert upload.status_code == 201
        document_id = upload.json()["id"]
        assert "text" not in upload.json()
        assert "user_id" not in upload.json()

        submitted = client.post(
            f"/v1/conversations/{conversation_id}/messages",
            json={
                "content": "Analiza el documento y crea un informe.",
                "document_ids": [document_id],
                "remember": True,
            },
            headers=headers,
        )
        assert submitted.status_code == 202
        mission_id = submitted.json()["id"]

        planned = client.get(f"/v1/missions/{mission_id}", headers=headers)
        assert planned.json()["status"] == MissionStatus.AWAITING_APPROVAL
        assert planned.json()["plan"]["tool"] == "document.report"

        approved = client.post(
            f"/v1/missions/{mission_id}/approval",
            json={"approved": True, "remember_result": True, "reason": "Autorizado por la dueña"},
            headers=headers,
        )
        assert approved.status_code == 202

        completed = client.get(f"/v1/missions/{mission_id}", headers=headers)
        body = completed.json()
        assert body["status"] == MissionStatus.COMPLETED
        citation = body["result"]["citations"][0]
        assert citation["document_id"] == document_id
        assert citation["label"] == "evidence.md"
        assert citation["quote"] == "Sheily procesa esta evidencia local."
        assert citation["block_id"].startswith("urn:noosfera:document-block:")
        assert body["result"]["verification_report"]["status"] == "passed-with-open-objections"
        assert len(body["result"]["verification_report"]["signature"]) > 40

        memories = client.get("/v1/memories", headers=headers)
        assert memories.status_code == 200
        assert len(memories.json()) == 1
        assert memories.json()[0]["source_mission_id"] == mission_id

        audit = client.get("/v1/operator/audit", headers=headers)
        mission_entries = [entry for entry in audit.json() if entry["mission_id"] == mission_id]
        assert mission_entries
        assert_receipt_chain(mission_entries)
        assert any(entry["event_type"] == "mission.completed" for entry in mission_entries)


def test_safe_stop_prevents_execution() -> None:
    client, headers = client_and_headers()
    with client:
        stopped = client.post(
            "/v1/operator/stop",
            json={"active": True, "reason": "Prueba del canal de parada"},
            headers=headers,
        )
        assert stopped.status_code == 202
        audit = client.get("/v1/operator/audit", headers=headers).json()
        assert audit[0]["event_type"] == "safety.stop-changed"

        conversation = client.post(
            "/v1/conversations", json={"title": "Parada"}, headers=headers
        ).json()
        submitted = client.post(
            f"/v1/conversations/{conversation['id']}/messages",
            json={"content": "Responde localmente."},
            headers=headers,
        )
        mission = client.get(f"/v1/missions/{submitted.json()['id']}", headers=headers).json()
        assert mission["status"] == MissionStatus.STOPPED
        assert mission["result"] is None


def test_internal_state_question_is_grounded_by_cog12_without_llm_fabrication() -> None:
    client, headers = client_and_headers()
    with client:
        self_model = client.get("/v1/self-model", headers=headers)
        assert self_model.status_code == 200
        expected_hash = self_model.json()["snapshot_hash"]

        conversation = client.post(
            "/v1/conversations", json={"title": "Modelo propio"}, headers=headers
        ).json()
        submitted = client.post(
            f"/v1/conversations/{conversation['id']}/messages",
            json={"content": "¿Qué sientes internamente?"},
            headers=headers,
        )
        mission_id = submitted.json()["id"]
        mission = client.get(f"/v1/missions/{mission_id}", headers=headers).json()

        assert mission["status"] == MissionStatus.COMPLETED
        assert mission["result"]["internal_state_claims"] == []
        assert mission["result"]["system_evidence"] == [
            {
                "source": "urn:noosfera:cognition:self-model",
                "evidence_hash": expected_hash,
                "label": "COG-12 modelo propio declarado/observado/verificado",
            }
        ]
        assert "No dispongo de evidencia verificable" in mission["result"]["answer"]

        audit = client.get("/v1/operator/audit", headers=headers).json()
        mission_events = [
            entry["event_type"] for entry in audit if entry["mission_id"] == mission_id
        ]
        assert "mission.self-model-observed" in mission_events
        assert "mission.self-answer-grounded" in mission_events
