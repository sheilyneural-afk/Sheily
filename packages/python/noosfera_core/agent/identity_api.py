"""API mínima de la autoridad de identidad; conserva las claves privadas aisladas."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from noosfera_core.agent.auth import AuthenticationError
from noosfera_core.agent.crypto import Ed25519Signer
from noosfera_core.agent.identity import IdentityAuthority
from noosfera_core.agent.models import ApprovalReceipt, LoginRequest, TokenResponse
from noosfera_core.config import Settings
from noosfera_core.manifest import load_service_manifest


class ApprovalIssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str
    plan_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    approved: bool
    remember_result: bool = False
    reason: str = Field(default="", max_length=1_000)


def create_identity_app(
    manifest_path: str | Path,
    *,
    settings: Settings | None = None,
    authority: IdentityAuthority | None = None,
) -> FastAPI:
    manifest = load_service_manifest(manifest_path)
    active = settings or Settings()
    active.assert_identity_safe()
    runtime = authority or IdentityAuthority(
        username=active.local_username,
        password=active.local_password,
        signer=Ed25519Signer(active.identity_private_key_b64, key_id=active.identity_key_id),
        token_ttl_seconds=active.token_ttl_seconds,
    )
    app = FastAPI(title="Sheily identity authority", version="0.3.0")

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"service": manifest.id, "status": "alive"}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        return {"service": manifest.id, "status": "ready", "key_id": runtime.signer.key_id}

    @app.post("/v1/auth/login", response_model=TokenResponse)
    async def login(request: LoginRequest) -> TokenResponse:
        try:
            return await runtime.login(request.username, request.password)
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    @app.post("/v1/approvals", response_model=ApprovalReceipt, status_code=201)
    async def approve(
        request: ApprovalIssueRequest, authorization: str | None = Header(default=None)
    ) -> ApprovalReceipt:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        try:
            return await runtime.approve(
                token=authorization.removeprefix("Bearer ").strip(),
                mission_id=request.mission_id,
                plan_hash=request.plan_hash,
                approved=request.approved,
                remember_result=request.remember_result,
                reason=request.reason,
            )
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    return app
