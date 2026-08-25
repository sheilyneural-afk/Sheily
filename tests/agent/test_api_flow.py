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
        governance_backend="deterministic-test",
        execution_backend="in-process-test",
        model_provider="deterministic",
        local_username="owner",
        local_password="correct-horse-battery-staple",  # noqa: S106 -- test credential
        token_secret="test-token-secret-with-at-least-32-characters",  # noqa: S106
        capability_secret="test-capability-secret-with-at-least-32-chars",  # noqa: S106
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
        assert body["result"]["citations"] == [{"document_id": document_id, "label": "evidence.md"}]

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
