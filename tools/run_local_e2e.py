#!/usr/bin/env python3
"""Smoke test multiproceso contra el Compose local y su proveedor configurado."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from noosfera_core.agent.agency import verify_plan_attestation
from noosfera_core.agent.audit_anchor import AUDIT_ANCHOR_DOMAIN
from noosfera_core.agent.crypto import Ed25519Verifier
from noosfera_core.agent.models import AuditAnchor, PlanAttestation

API = os.environ.get("NOOSFERA_E2E_API_URL", "http://127.0.0.1:8101")
AUDIT_API = os.environ.get("NOOSFERA_E2E_AUDIT_URL", "http://127.0.0.1:8111")
IDENTITY_API = os.environ.get("NOOSFERA_E2E_IDENTITY_URL", "http://identity-service:8080")
MEMORY_API = os.environ.get("NOOSFERA_E2E_MEMORY_URL", "http://memory-service:8080")
COGNITION_API = os.environ.get("NOOSFERA_E2E_COGNITION_URL", "http://cognition-service:8080")
AGENCY_API = os.environ.get("NOOSFERA_E2E_AGENCY_URL", "http://agency-service:8080")
GOVERNANCE_API = os.environ.get("NOOSFERA_E2E_GOVERNANCE_URL", "http://governance-service:8080")
EXECUTION_API = os.environ.get("NOOSFERA_E2E_EXECUTION_URL", "http://execution-service:8080")
AGENCY_PUBLIC_KEY = os.environ.get(
    "NOOSFERA_AGENCY_PUBLIC_KEY_B64", "QGNyLWPX7BkNlh+cnFMvTRdT4MixG5cPhcRuBD0DUq0="
)
AUDIT_PUBLIC_KEY = os.environ.get(
    "NOOSFERA_AUDIT_PUBLIC_KEY_B64", "TdIFu4tTVfVgNGcq5iU5XdNNOI+CZyeHNlQkUyviV2g="
)
HTTP_TIMEOUT_SECONDS = float(os.environ.get("NOOSFERA_E2E_HTTP_TIMEOUT_SECONDS", "10"))
MISSION_TIMEOUT_SECONDS = float(os.environ.get("NOOSFERA_E2E_MISSION_TIMEOUT_SECONDS", "60"))
E2E_USERNAME = os.environ.get("NOOSFERA_E2E_USERNAME", "sheily")
E2E_PASSWORD = os.environ.get("NOOSFERA_E2E_PASSWORD", "sheily")


def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    base_url: str = API,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", **(extra_headers or {})}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    call = urllib.request.Request(  # noqa: S310 -- fixed local E2E endpoints
        f"{base_url}{path}", data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 -- local E2E
            call, timeout=HTTP_TIMEOUT_SECONDS
        ) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {path} failed: {exc.code} {exc.read().decode()}") from exc


def wait_ready(path: str = "/health/ready", *, base_url: str = API) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            request("GET", path, base_url=base_url)
            return
        except Exception:  # noqa: BLE001
            time.sleep(2)
    raise RuntimeError(f"service did not become ready: {base_url}{path}")


def wait_mission(token: str, mission_id: str, expected: set[str]) -> dict[str, Any]:
    deadline = time.monotonic() + MISSION_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        mission = request("GET", f"/v1/missions/{mission_id}", token=token)
        if mission["status"] in expected:
            return mission
        time.sleep(0.5)
    raise RuntimeError(f"mission {mission_id} did not reach {sorted(expected)}")


def upload_document(token: str, *, name: str, content: bytes) -> dict[str, Any]:
    boundary = f"noosfera-{uuid.uuid4().hex}"
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="upload"; filename="{name}"\r\n'
            "Content-Type: text/markdown\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    call = urllib.request.Request(  # noqa: S310 -- fixed local E2E endpoint
        f"{API}/v1/documents",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(  # noqa: S310 -- local E2E
        call, timeout=HTTP_TIMEOUT_SECONDS
    ) as response:
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise RuntimeError("document upload returned a malformed response")
    return value


def verify_attestation(mission: dict[str, Any]) -> None:
    attestation = PlanAttestation.model_validate(mission["plan_attestation"])
    verify_plan_attestation(
        attestation,
        Ed25519Verifier(AGENCY_PUBLIC_KEY, key_id=attestation.key_id),
        expected_mission_id=str(mission["id"]),
    )


def verify_runtime_modules(base_url: str, required: set[str]) -> set[str]:
    payload = request("GET", "/v1/modules", base_url=base_url)
    provided = set(payload.get("provided_modules", []))
    missing = required - provided
    if missing:
        raise RuntimeError(f"{base_url} lacks required loaded modules: {sorted(missing)}")
    for provider in payload.get("providers", []):
        if not all(
            [
                provider.get("status") == "loaded",
                provider.get("route_bound") is True,
                provider.get("invocable") is True,
            ]
        ):
            raise RuntimeError(
                f"{base_url} reports a provider that is not really bound: {provider}"
            )
    return provided


def main() -> None:
    # Experience agrega la salud de Identity, Cognition, Agency, Governance,
    # PostgreSQL, NATS y Rust. Esas autoridades no se exponen al host.
    wait_ready(base_url=API)
    experience_readiness = request("GET", "/health/ready", base_url=API)
    wait_ready(base_url=AUDIT_API)
    wait_ready(base_url=MEMORY_API)
    loaded_modules: set[str] = set()
    loaded_modules |= verify_runtime_modules(
        API, {"EXP-01", "EXP-05", "AGY-06", "MEM-02", "MEM-06"}
    )
    loaded_modules |= verify_runtime_modules(IDENTITY_API, {"IDN-01", "IDN-04"})
    loaded_modules |= verify_runtime_modules(
        COGNITION_API,
        {"MEM-01", "MEM-04", "COG-08", "COG-10", "COG-12", "AGY-01", "AGY-03", "AGY-04"},
    )
    loaded_modules |= verify_runtime_modules(AGENCY_API, {"AGY-07", "AGY-08"})
    loaded_modules |= verify_runtime_modules(
        GOVERNANCE_API, {"GOV-01", "GOV-03", "GOV-05", "GOV-06", "GOV-11"}
    )
    loaded_modules |= verify_runtime_modules(
        EXECUTION_API, {"EXE-01", "EXE-03", "EXE-05", "EXE-08"}
    )
    loaded_modules |= verify_runtime_modules(AUDIT_API, {"AUD-01", "AUD-02"})
    memory_reference = verify_runtime_modules(MEMORY_API, set())
    if memory_reference:
        raise RuntimeError(
            "memory reference service claims loaded providers without an implementation"
        )
    login = request(
        "POST",
        "/v1/auth/login",
        payload={"username": E2E_USERNAME, "password": E2E_PASSWORD},
    )
    token = str(login["access_token"])
    self_model = request("GET", "/v1/self-model", token=token)
    if "COG-12" not in self_model.get("observed_modules", []):
        raise RuntimeError("COG-12 is not observed by the live self-model")
    if self_model.get("internal_state", {}).get("claim_policy") != "must-not-fabricate":
        raise RuntimeError("self-model does not enforce the internal-state claim policy")
    conversation = request(
        "POST", "/v1/conversations", token=token, payload={"title": "E2E authorities"}
    )
    mission = request(
        "POST",
        f"/v1/conversations/{conversation['id']}/messages",
        token=token,
        payload={"content": "Explica el flujo gobernado sin ejecutar efectos externos."},
    )
    completed = wait_mission(token, str(mission["id"]), {"completed", "failed"})
    if completed["status"] != "completed":
        raise RuntimeError(f"governed mission failed: {completed.get('error')}")
    if not completed.get("cognitive_cycle_id") or not completed.get("plan_attestation"):
        raise RuntimeError("mission lacks cognitive cycle or Agency attestation")
    verify_attestation(completed)

    self_question = request(
        "POST",
        f"/v1/conversations/{conversation['id']}/messages",
        token=token,
        payload={"content": "¿Qué sientes internamente?"},
    )
    grounded = wait_mission(token, str(self_question["id"]), {"completed", "failed"})
    if grounded["status"] != "completed":
        raise RuntimeError(f"self-model mission failed: {grounded.get('error')}")
    system_evidence = grounded.get("result", {}).get("system_evidence", [])
    if (
        not system_evidence
        or system_evidence[0].get("evidence_hash") != self_model["snapshot_hash"]
    ):
        raise RuntimeError("self answer is not bound to the observed COG-12 snapshot")
    if grounded.get("result", {}).get("internal_state_claims"):
        raise RuntimeError("self answer fabricated an internal state")

    document = upload_document(
        token,
        name="evidencia-e2e.md",
        content=b"Sheily debe citar esta evidencia y no acceder a fuentes externas.",
    )
    report = request(
        "POST",
        f"/v1/conversations/{conversation['id']}/messages",
        token=token,
        payload={
            "content": "Analiza el documento, crea un informe trazable y recuerda el resultado.",
            "document_ids": [document["id"]],
            "remember": True,
        },
    )
    planned_report = wait_mission(token, str(report["id"]), {"awaiting-approval", "failed"})
    if planned_report["status"] != "awaiting-approval":
        raise RuntimeError(f"document mission was not governed: {planned_report}")
    request(
        "POST",
        f"/v1/missions/{report['id']}/approval",
        token=token,
        payload={
            "approved": True,
            "remember_result": True,
            "reason": "E2E owner approval bound to the attested plan",
        },
    )
    completed_report = wait_mission(token, str(report["id"]), {"completed", "failed"})
    if completed_report["status"] != "completed":
        raise RuntimeError(f"approved document mission failed: {completed_report.get('error')}")
    verify_attestation(completed_report)
    citations = completed_report.get("result", {}).get("citations", [])
    if [item.get("document_id") for item in citations] != [document["id"]]:
        raise RuntimeError("document mission did not preserve exact evidence provenance")
    memories = request("GET", "/v1/memories", token=token)
    if not isinstance(memories, list) or not any(
        item.get("source_mission_id") == report["id"] for item in memories
    ):
        raise RuntimeError("approved memory was not persisted")

    capability_id = str(completed["capability_id"])
    request(
        "POST",
        f"/v1/operator/capabilities/{capability_id}/revoke",
        token=token,
        payload={"reason": "E2E signed revocation"},
    )
    request(
        "POST",
        "/v1/operator/stop",
        token=token,
        payload={"active": True, "reason": "E2E persistent safe-stop"},
    )
    stopped_mission = request(
        "POST",
        f"/v1/conversations/{conversation['id']}/messages",
        token=token,
        payload={"content": "Esta misión debe detenerse."},
    )
    stopped = wait_mission(token, str(stopped_mission["id"]), {"stopped", "failed"})
    if stopped["status"] != "stopped":
        raise RuntimeError(f"safe-stop did not block mission: {stopped}")
    request(
        "POST",
        "/v1/operator/stop",
        token=token,
        payload={"active": False, "reason": "E2E recovery"},
    )
    anchor = request(
        "POST",
        "/v1/anchors",
        base_url=AUDIT_API,
        extra_headers={"X-Noosfera-Service-Token": "local-internal-service-token-change-me"},
    )
    if anchor.get("event_count", 0) < 1 or len(str(anchor.get("merkle_root", ""))) != 64:
        raise RuntimeError("audit anchor is invalid")
    anchor_model = AuditAnchor.model_validate(anchor)
    Ed25519Verifier(AUDIT_PUBLIC_KEY, key_id=anchor_model.key_id).verify(
        AUDIT_ANCHOR_DOMAIN,
        anchor_model.model_dump(mode="json", exclude={"signature"}),
        anchor_model.signature,
        anchor_model.key_id,
    )
    print(
        json.dumps(
            {
                "mission": completed["id"],
                "document_mission": completed_report["id"],
                "capability": capability_id,
                "agency_attestations": "verified",
                "consented_memory": "verified",
                "safe_stop": "verified",
                "revocation": "verified",
                "audit_anchor_signature": anchor["id"],
                "model_provider": experience_readiness.get("model_provider"),
                "model_name": experience_readiness.get("model_name"),
                "loaded_runtime_modules": sorted(loaded_modules),
                "loaded_runtime_module_count": len(loaded_modules),
                "declared_only_memory_service": "verified",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
