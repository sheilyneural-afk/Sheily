"""Autoridad independiente que verifica planes/consentimiento y emite capacidades."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Protocol

import httpx

from noosfera_core.agent.agency import verify_plan_attestation
from noosfera_core.agent.crypto import Ed25519Signer, Ed25519Verifier
from noosfera_core.agent.governance import GovernanceEngine, GovernanceRejected
from noosfera_core.agent.identity import APPROVAL_DOMAIN
from noosfera_core.agent.models import (
    ApprovalReceipt,
    CapabilityGrant,
    PlanAttestation,
    RevocationDirective,
    RiskDecision,
    StopDirective,
    new_id,
    utc_now,
)
from noosfera_core.hashing import canonical_hash

CAPABILITY_DOMAIN = "noosfera.governance.capability.v1"
STOP_DOMAIN = "noosfera.governance.stop-directive.v1"
REVOCATION_DOMAIN = "noosfera.governance.revocation-directive.v1"


class GovernanceGateway(Protocol):
    name: str

    async def health(self) -> bool: ...

    async def evaluate(
        self, attestation: PlanAttestation, *, has_documents: bool, remember: bool
    ) -> RiskDecision: ...

    async def issue_capability(
        self,
        attestation: PlanAttestation,
        *,
        has_documents: bool,
        remember: bool,
        parameters_hash: str,
        approval: ApprovalReceipt | None,
    ) -> CapabilityGrant: ...

    async def authorize_memory(self, *, user_id: str, approval: ApprovalReceipt | None) -> None: ...

    async def issue_stop(
        self, *, active: bool, reason: str, approval: ApprovalReceipt
    ) -> StopDirective: ...

    async def issue_revocation(
        self, *, capability_id: str, reason: str, approval: ApprovalReceipt
    ) -> RevocationDirective: ...


def _without_signature(value: ApprovalReceipt | StopDirective) -> dict[str, Any]:
    return value.model_dump(mode="json", exclude={"signature"})


class GovernanceStore:
    """Ledger idempotente de decisiones y secuencia monotónica de parada."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url
        self._pool: Any = None
        self._grants: dict[str, CapabilityGrant] = {}
        self._stop_version = 0

    async def initialize(self) -> None:
        if self.database_url is None:
            return
        import asyncpg  # type: ignore[import-untyped]

        self._pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        await self._pool.execute(
            """CREATE TABLE IF NOT EXISTS governance_grants (
                 authorization_key TEXT PRIMARY KEY, capability_id TEXT NOT NULL UNIQUE,
                 grant_payload JSONB NOT NULL, issued_at TIMESTAMPTZ NOT NULL
               );
               CREATE TABLE IF NOT EXISTS governance_control (
                 singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
                 stop_version BIGINT NOT NULL DEFAULT 0,
                 revocation_version BIGINT NOT NULL DEFAULT 0
               );
               ALTER TABLE governance_control
                 ADD COLUMN IF NOT EXISTS revocation_version BIGINT NOT NULL DEFAULT 0;
               INSERT INTO governance_control(singleton,stop_version,revocation_version)
                 VALUES(TRUE,0,0)
                 ON CONFLICT(singleton) DO NOTHING;"""
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def health(self) -> bool:
        if self.database_url is None:
            return True
        try:
            return bool(self._pool and await self._pool.fetchval("SELECT 1"))
        except Exception:  # noqa: BLE001
            return False

    async def record_or_get(
        self, authorization_key: str, grant: CapabilityGrant
    ) -> CapabilityGrant:
        if self._pool is None:
            existing = self._grants.setdefault(authorization_key, grant)
            return existing
        row = await self._pool.fetchrow(
            """INSERT INTO governance_grants
                 (authorization_key,capability_id,grant_payload,issued_at)
               VALUES($1,$2,$3::jsonb,$4)
               ON CONFLICT(authorization_key) DO UPDATE
                 SET authorization_key=EXCLUDED.authorization_key
               RETURNING grant_payload""",
            authorization_key,
            str(grant.capability["id"]),
            grant.model_dump_json(),
            utc_now(),
        )
        payload = row["grant_payload"]
        return CapabilityGrant.model_validate(
            json.loads(payload) if isinstance(payload, str) else payload
        )

    async def next_stop_version(self) -> int:
        if self._pool is None:
            self._stop_version += 1
            return self._stop_version
        return int(
            await self._pool.fetchval(
                """UPDATE governance_control SET stop_version=stop_version+1
                   WHERE singleton=TRUE RETURNING stop_version"""
            )
        )

    async def next_revocation_version(self) -> int:
        if self._pool is None:
            self._stop_version += 1
            return self._stop_version
        return int(
            await self._pool.fetchval(
                """UPDATE governance_control SET revocation_version=revocation_version+1
                   WHERE singleton=TRUE RETURNING revocation_version"""
            )
        )


class GovernanceAuthority:
    name = "ed25519-governance-authority"

    def __init__(
        self,
        *,
        policy: GovernanceEngine,
        signer: Ed25519Signer,
        agency_verifier: Ed25519Verifier,
        identity_verifier: Ed25519Verifier,
        store: GovernanceStore,
        capability_ttl_seconds: int,
    ) -> None:
        self.policy = policy
        self.signer = signer
        self.agency_verifier = agency_verifier
        self.identity_verifier = identity_verifier
        self.store = store
        self.capability_ttl_seconds = capability_ttl_seconds

    async def initialize(self) -> None:
        await self.store.initialize()

    async def close(self) -> None:
        await self.store.close()

    async def health(self) -> bool:
        policy, ledger = await self.policy.health(), await self.store.health()
        return policy and ledger

    def _verify_attestation(self, value: PlanAttestation) -> None:
        verify_plan_attestation(value, self.agency_verifier)

    def _verify_approval(
        self,
        approval: ApprovalReceipt,
        *,
        mission_id: str,
        user_id: str,
        plan_hash: str,
        remember: bool,
    ) -> None:
        self.identity_verifier.verify(
            APPROVAL_DOMAIN,
            _without_signature(approval),
            approval.signature,
            approval.key_id,
        )
        if approval.expiry <= utc_now():
            raise GovernanceRejected("approval receipt expired")
        if not approval.approved:
            raise GovernanceRejected("user rejected the mission")
        if (
            approval.mission_id != mission_id
            or approval.user_id != user_id
            or approval.plan_hash != plan_hash
        ):
            raise GovernanceRejected("approval is not bound to this user, mission and plan")
        if remember and not approval.remember_result:
            raise GovernanceRejected("approval does not permit persistent memory")

    async def evaluate(
        self, attestation: PlanAttestation, *, has_documents: bool, remember: bool
    ) -> RiskDecision:
        self._verify_attestation(attestation)
        if attestation.plan.requires_documents != has_documents:
            raise GovernanceRejected("document scope changed after Agency attestation")
        return await self.policy.evaluate_mission(
            attestation.plan, has_documents=has_documents, remember=remember
        )

    async def issue_capability(
        self,
        attestation: PlanAttestation,
        *,
        has_documents: bool,
        remember: bool,
        parameters_hash: str,
        approval: ApprovalReceipt | None,
    ) -> CapabilityGrant:
        risk = await self.evaluate(attestation, has_documents=has_documents, remember=remember)
        if risk.requires_approval:
            if approval is None:
                raise GovernanceRejected("a signed owner approval is required")
            self._verify_approval(
                approval,
                mission_id=attestation.mission_id,
                user_id=attestation.user_id,
                plan_hash=attestation.plan_hash,
                remember=remember,
            )
            authorization_key = approval.id
            quorum_proof = approval.id
        else:
            authorization_key = f"auto:{attestation.mission_id}:{attestation.plan_hash}"
            quorum_proof = f"urn:noosfera:policy:auto:{attestation.mission_id.rsplit(':', 1)[-1]}"
        now = utc_now()
        budget = attestation.budget
        authorization_precondition = (
            "owner-authorized" if risk.requires_approval else "policy-auto-authorized"
        )
        capability: dict[str, Any] = {
            "id": new_id("capability"),
            "issuer": "urn:noosfera:service:governance",
            "holder": "urn:noosfera:service:experience",
            "mission_id": attestation.mission_id,
            "user_id": attestation.user_id,
            "resource": attestation.plan.resource,
            "permitted_operations": [attestation.plan.operation],
            "plan_hash": attestation.plan_hash,
            "arguments_hash": parameters_hash,
            "bounds": {
                "output_bytes": {"unit": "bytes", "maximum": budget.output_bytes},
                "input_bytes": {"unit": "bytes", "maximum": budget.input_bytes},
                "wall_time": {"unit": "seconds", "maximum": budget.wall_time_seconds},
                "cpu_time": {"unit": "milliseconds", "maximum": budget.cpu_time_ms},
                "memory": {"unit": "bytes", "maximum": budget.memory_bytes},
                "model_input_tokens": {
                    "unit": "tokens",
                    "maximum": budget.model_input_tokens,
                },
                "model_output_tokens": {
                    "unit": "tokens",
                    "maximum": budget.model_output_tokens,
                },
                "cost": {"unit": "microunits", "maximum": budget.cost_microunits},
                "tool_calls": {"unit": "calls", "maximum": budget.max_tool_calls},
                "child_processes": {
                    "unit": "processes",
                    "maximum": budget.max_child_processes,
                },
            },
            "preconditions": [
                "agency-attested",
                authorization_precondition,
                "local-model-only",
            ],
            "mandatory_monitors": [
                "urn:noosfera:monitor:model-local",
                "urn:noosfera:monitor:stop-channel",
                "urn:noosfera:monitor:capability-ledger",
            ],
            "stop_conditions": ["user-stop", "monitor-loss", "budget-exhausted"],
            "not_before": now.isoformat().replace("+00:00", "Z"),
            "expiry": (now + timedelta(seconds=self.capability_ttl_seconds))
            .isoformat()
            .replace("+00:00", "Z"),
            "max_uses": 1,
            "delegation": "forbidden",
            "network_allowed": budget.network_allowed,
            "quorum_proof": quorum_proof,
        }
        signature = self.signer.sign(CAPABILITY_DOMAIN, capability)
        grant = CapabilityGrant(
            capability=capability,
            key_id=self.signer.key_id,
            signature=signature,
        )
        return await self.store.record_or_get(authorization_key, grant)

    async def authorize_memory(self, *, user_id: str, approval: ApprovalReceipt | None) -> None:
        if approval is None or approval.user_id != user_id or not approval.remember_result:
            raise GovernanceRejected("signed owner approval is required for memory")
        self.identity_verifier.verify(
            APPROVAL_DOMAIN,
            _without_signature(approval),
            approval.signature,
            approval.key_id,
        )
        await self.policy.authorize_memory(user_id=user_id, owner_confirmation=True)

    async def issue_stop(
        self, *, active: bool, reason: str, approval: ApprovalReceipt
    ) -> StopDirective:
        directive_hash = canonical_hash({"active": active, "reason": reason})
        expected_mission = "urn:noosfera:mission:operator-control"
        self._verify_approval(
            approval,
            mission_id=expected_mission,
            user_id=approval.user_id,
            plan_hash=directive_hash,
            remember=False,
        )
        version = await self.store.next_stop_version()
        pending = StopDirective(
            id=new_id("stop-directive"),
            active=active,
            reason=reason,
            version=version,
            issued_by=approval.user_id,
            issued_at=utc_now(),
            key_id=self.signer.key_id,
            signature="pending",
        )
        signature = self.signer.sign(STOP_DOMAIN, _without_signature(pending))
        return pending.model_copy(update={"signature": signature})

    async def issue_revocation(
        self, *, capability_id: str, reason: str, approval: ApprovalReceipt
    ) -> RevocationDirective:
        directive_hash = canonical_hash({"capability_id": capability_id, "reason": reason})
        self._verify_approval(
            approval,
            mission_id="urn:noosfera:mission:operator-control",
            user_id=approval.user_id,
            plan_hash=directive_hash,
            remember=False,
        )
        version = await self.store.next_revocation_version()
        pending = RevocationDirective(
            id=new_id("revocation-directive"),
            capability_id=capability_id,
            reason=reason,
            version=version,
            issued_by=approval.user_id,
            issued_at=utc_now(),
            key_id=self.signer.key_id,
            signature="pending",
        )
        payload = pending.model_dump(mode="json", exclude={"signature"})
        return pending.model_copy(
            update={"signature": self.signer.sign(REVOCATION_DOMAIN, payload)}
        )


class RemoteGovernanceClient:
    name = "remote-governance-service"

    def __init__(self, base_url: str, *, service_token: str, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}{path}",
                    headers={"X-Noosfera-Service-Token": self.service_token},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise GovernanceRejected("governance service is unavailable") from exc
        if response.status_code not in {200, 201}:
            raise GovernanceRejected(f"governance rejected request: {response.text[:500]}")
        value = response.json()
        if not isinstance(value, dict):
            raise GovernanceRejected("governance returned a malformed response")
        return value

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/health/ready")
                return response.is_success
        except httpx.HTTPError:
            return False

    async def evaluate(
        self, attestation: PlanAttestation, *, has_documents: bool, remember: bool
    ) -> RiskDecision:
        value = await self._post(
            "/v1/decisions/evaluate",
            {
                "attestation": attestation.model_dump(mode="json"),
                "has_documents": has_documents,
                "remember": remember,
            },
        )
        return RiskDecision.model_validate(value)

    async def issue_capability(
        self,
        attestation: PlanAttestation,
        *,
        has_documents: bool,
        remember: bool,
        parameters_hash: str,
        approval: ApprovalReceipt | None,
    ) -> CapabilityGrant:
        value = await self._post(
            "/v1/capabilities",
            {
                "attestation": attestation.model_dump(mode="json"),
                "has_documents": has_documents,
                "remember": remember,
                "parameters_hash": parameters_hash,
                "approval": approval.model_dump(mode="json") if approval else None,
            },
        )
        return CapabilityGrant.model_validate(value)

    async def authorize_memory(self, *, user_id: str, approval: ApprovalReceipt | None) -> None:
        await self._post(
            "/v1/memory/authorize",
            {
                "user_id": user_id,
                "approval": approval.model_dump(mode="json") if approval else None,
            },
        )

    async def issue_stop(
        self, *, active: bool, reason: str, approval: ApprovalReceipt
    ) -> StopDirective:
        value = await self._post(
            "/v1/stop-directives",
            {"active": active, "reason": reason, "approval": approval.model_dump(mode="json")},
        )
        return StopDirective.model_validate(value)

    async def issue_revocation(
        self, *, capability_id: str, reason: str, approval: ApprovalReceipt
    ) -> RevocationDirective:
        value = await self._post(
            "/v1/revocation-directives",
            {
                "capability_id": capability_id,
                "reason": reason,
                "approval": approval.model_dump(mode="json"),
            },
        )
        return RevocationDirective.model_validate(value)
