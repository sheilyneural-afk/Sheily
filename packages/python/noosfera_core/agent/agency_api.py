"""API interna de Agency."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from noosfera_core.agent.agency import AgencyAuthority, AgencyRejected
from noosfera_core.agent.crypto import Ed25519Signer
from noosfera_core.agent.models import MissionPlan, PlanAttestation, ResourceBudget
from noosfera_core.config import Settings
from noosfera_core.manifest import load_service_manifest
from noosfera_core.module_registry import install_runtime_module_registry


class AttestationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str
    user_id: str
    prompt_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    context_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    plan: MissionPlan
    budget: ResourceBudget


def create_agency_app(
    manifest_path: str | Path,
    *,
    settings: Settings | None = None,
    authority: AgencyAuthority | None = None,
) -> FastAPI:
    manifest = load_service_manifest(manifest_path)
    active = settings or Settings()
    active.assert_agency_safe()
    runtime = authority or AgencyAuthority(
        Ed25519Signer(active.agency_private_key_b64, key_id=active.agency_key_id)
    )
    app = FastAPI(title="Sheily agency authority", version="0.3.0")

    def authorize(token: str | None) -> None:
        if token is None or not secrets.compare_digest(token, active.internal_service_token):
            raise HTTPException(status_code=401, detail="invalid service identity")

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"service": manifest.id, "status": "alive"}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        return {"service": manifest.id, "status": "ready", "key_id": runtime.signer.key_id}

    @app.post("/v1/plans/attest", response_model=PlanAttestation, status_code=201)
    async def attest(
        request: AttestationRequest,
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> PlanAttestation:
        authorize(service_token)
        try:
            return await runtime.attest(
                mission_id=request.mission_id,
                user_id=request.user_id,
                prompt_hash=request.prompt_hash,
                context_hash=request.context_hash,
                plan=request.plan,
                budget=request.budget,
            )
        except AgencyRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return install_runtime_module_registry(app, manifest)
