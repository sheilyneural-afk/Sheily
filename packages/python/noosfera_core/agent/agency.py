"""Frontera de Agency: valida, limita y atesta planes; nunca emite capacidades."""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

import httpx

from noosfera_core.agent.crypto import Ed25519Signer, Ed25519Verifier
from noosfera_core.agent.models import MissionPlan, PlanAttestation, ResourceBudget, utc_now
from noosfera_core.hashing import canonical_hash

PLAN_DOMAIN = "noosfera.agency.plan-attestation.v1"


class AgencyRejected(RuntimeError):
    pass


class AgencyGateway(Protocol):
    name: str

    async def health(self) -> bool: ...

    async def attest(
        self,
        *,
        mission_id: str,
        user_id: str,
        prompt_hash: str,
        context_hash: str,
        plan: MissionPlan,
        budget: ResourceBudget,
    ) -> PlanAttestation: ...


def unsigned_attestation(attestation: PlanAttestation) -> dict[str, object]:
    return attestation.model_dump(mode="json", exclude={"signature"})


def verify_plan_attestation(
    attestation: PlanAttestation,
    verifier: Ed25519Verifier,
    *,
    expected_mission_id: str | None = None,
) -> None:
    if expected_mission_id and attestation.mission_id != expected_mission_id:
        raise AgencyRejected("plan attestation belongs to another mission")
    if attestation.expiry <= utc_now():
        raise AgencyRejected("plan attestation expired")
    if canonical_hash(attestation.plan.model_dump(mode="json")) != attestation.plan_hash:
        raise AgencyRejected("attested plan hash is invalid")
    verifier.verify(
        PLAN_DOMAIN,
        unsigned_attestation(attestation),
        attestation.signature,
        attestation.key_id,
    )


class AgencyAuthority:
    name = "ed25519-agency-authority"

    def __init__(self, signer: Ed25519Signer, *, attestation_ttl_seconds: int = 300) -> None:
        self.signer = signer
        self.attestation_ttl_seconds = attestation_ttl_seconds

    async def health(self) -> bool:
        return True

    @staticmethod
    def _validate_plan(plan: MissionPlan, budget: ResourceBudget) -> None:
        allowed = {
            "conversation.answer": ("answer", "urn:noosfera:tool:conversation-answer", False),
            "document.report": ("generate", "urn:noosfera:tool:document-report", True),
        }
        expected = allowed[plan.tool]
        if (plan.operation, plan.resource, plan.requires_documents) != expected:
            raise AgencyRejected("plan tool, operation, resource and evidence scope disagree")
        if [step.index for step in plan.steps] != list(range(1, len(plan.steps) + 1)):
            raise AgencyRejected("plan steps must be contiguous and start at one")
        if budget.network_allowed or budget.max_child_processes != 0:
            raise AgencyRejected("reference Agency forbids network and child processes")
        if budget.max_tool_calls != 1:
            raise AgencyRejected("reference Agency permits exactly one tool call")

    async def attest(
        self,
        *,
        mission_id: str,
        user_id: str,
        prompt_hash: str,
        context_hash: str,
        plan: MissionPlan,
        budget: ResourceBudget,
    ) -> PlanAttestation:
        self._validate_plan(plan, budget)
        now = utc_now()
        body = {
            "mission_id": mission_id,
            "user_id": user_id,
            "agent_id": "urn:noosfera:agent:sheily",
            "prompt_hash": prompt_hash,
            "context_hash": context_hash,
            "plan": plan,
            "plan_hash": canonical_hash(plan.model_dump(mode="json")),
            "budget": budget,
            "created_at": now,
            "expiry": now + timedelta(seconds=self.attestation_ttl_seconds),
            "key_id": self.signer.key_id,
            "algorithm": "Ed25519",
        }
        pending = PlanAttestation.model_validate({**body, "signature": "pending"})
        signature = self.signer.sign(PLAN_DOMAIN, unsigned_attestation(pending))
        return pending.model_copy(update={"signature": signature})


class RemoteAgencyClient:
    name = "remote-agency-service"

    def __init__(self, base_url: str, *, service_token: str, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/health/ready")
                return response.is_success
        except httpx.HTTPError:
            return False

    async def attest(
        self,
        *,
        mission_id: str,
        user_id: str,
        prompt_hash: str,
        context_hash: str,
        plan: MissionPlan,
        budget: ResourceBudget,
    ) -> PlanAttestation:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/v1/plans/attest",
                    headers={"X-Noosfera-Service-Token": self.service_token},
                    json={
                        "mission_id": mission_id,
                        "user_id": user_id,
                        "prompt_hash": prompt_hash,
                        "context_hash": context_hash,
                        "plan": plan.model_dump(mode="json"),
                        "budget": budget.model_dump(mode="json"),
                    },
                )
        except httpx.HTTPError as exc:
            raise AgencyRejected("Agency service is unavailable") from exc
        if response.status_code != 201:
            raise AgencyRejected(f"Agency rejected plan: {response.text[:500]}")
        return PlanAttestation.model_validate(response.json())
