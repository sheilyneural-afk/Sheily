"""API interna de Governance, única emisora de capacidades y paradas."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from noosfera_core.agent.crypto import Ed25519Signer, Ed25519Verifier
from noosfera_core.agent.governance import GovernanceRejected, OpaGovernance
from noosfera_core.agent.governance_authority import GovernanceAuthority, GovernanceStore
from noosfera_core.agent.models import (
    ApprovalReceipt,
    CapabilityGrant,
    PlanAttestation,
    RevocationDirective,
    RiskDecision,
    StopDirective,
)
from noosfera_core.config import Settings
from noosfera_core.manifest import load_service_manifest
from noosfera_core.module_registry import install_runtime_module_registry
from noosfera_core.policy import OpaClient


class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attestation: PlanAttestation
    has_documents: bool
    remember: bool


class CapabilityRequest(EvaluateRequest):
    parameters_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    approval: ApprovalReceipt | None = None


class MemoryAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    approval: ApprovalReceipt | None


class StopDirectiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool
    reason: str = Field(min_length=1, max_length=500)
    approval: ApprovalReceipt


class RevocationDirectiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    reason: str = Field(min_length=1, max_length=500)
    approval: ApprovalReceipt


def create_governance_app(
    manifest_path: str | Path,
    *,
    settings: Settings | None = None,
    authority: GovernanceAuthority | None = None,
) -> FastAPI:
    manifest = load_service_manifest(manifest_path)
    active = settings or Settings()
    active.assert_governance_safe()
    runtime = authority or GovernanceAuthority(
        policy=OpaGovernance(OpaClient(active.opa_url)),
        signer=Ed25519Signer(active.governance_private_key_b64, key_id=active.governance_key_id),
        agency_verifier=Ed25519Verifier(active.agency_public_key_b64, key_id=active.agency_key_id),
        identity_verifier=Ed25519Verifier(
            active.identity_public_key_b64, key_id=active.identity_key_id
        ),
        store=GovernanceStore(active.database_url),
        capability_ttl_seconds=active.capability_ttl_seconds,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        await runtime.initialize()
        try:
            yield
        finally:
            await runtime.close()

    app = FastAPI(title="Sheily governance authority", version="0.3.0", lifespan=lifespan)

    def authorize(token: str | None) -> None:
        if token is None or not secrets.compare_digest(token, active.internal_service_token):
            raise HTTPException(status_code=401, detail="invalid service identity")

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"service": manifest.id, "status": "alive"}

    @app.get("/health/ready")
    async def ready() -> dict[str, object]:
        if not await runtime.health():
            raise HTTPException(status_code=503, detail="policy or decision ledger unavailable")
        return {"service": manifest.id, "status": "ready", "key_id": runtime.signer.key_id}

    @app.post("/v1/decisions/evaluate", response_model=RiskDecision)
    async def evaluate(
        request: EvaluateRequest,
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> RiskDecision:
        authorize(service_token)
        try:
            return await runtime.evaluate(
                request.attestation,
                has_documents=request.has_documents,
                remember=request.remember,
            )
        except (GovernanceRejected, ValueError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/v1/capabilities", response_model=CapabilityGrant, status_code=201)
    async def issue_capability(
        request: CapabilityRequest,
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> CapabilityGrant:
        authorize(service_token)
        try:
            return await runtime.issue_capability(
                request.attestation,
                has_documents=request.has_documents,
                remember=request.remember,
                parameters_hash=request.parameters_hash,
                approval=request.approval,
            )
        except (GovernanceRejected, ValueError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/v1/memory/authorize")
    async def authorize_memory(
        request: MemoryAuthorizationRequest,
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> dict[str, bool]:
        authorize(service_token)
        try:
            await runtime.authorize_memory(user_id=request.user_id, approval=request.approval)
            return {"authorized": True}
        except (GovernanceRejected, ValueError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/v1/stop-directives", response_model=StopDirective, status_code=201)
    async def issue_stop(
        request: StopDirectiveRequest,
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> StopDirective:
        authorize(service_token)
        try:
            return await runtime.issue_stop(
                active=request.active, reason=request.reason, approval=request.approval
            )
        except (GovernanceRejected, ValueError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/v1/revocation-directives", response_model=RevocationDirective, status_code=201)
    async def issue_revocation(
        request: RevocationDirectiveRequest,
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> RevocationDirective:
        authorize(service_token)
        try:
            return await runtime.issue_revocation(
                capability_id=request.capability_id,
                reason=request.reason,
                approval=request.approval,
            )
        except (GovernanceRejected, ValueError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    return install_runtime_module_registry(app, manifest)
