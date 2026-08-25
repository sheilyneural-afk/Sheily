"""API del custodio de auditoría independiente."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query

from noosfera_core.agent.audit_anchor import AuditAnchorStore, AuditIntegrityError
from noosfera_core.agent.crypto import Ed25519Signer
from noosfera_core.agent.models import AuditAnchor
from noosfera_core.config import Settings
from noosfera_core.manifest import load_service_manifest


def create_audit_app(
    manifest_path: str | Path,
    *,
    settings: Settings | None = None,
    store: AuditAnchorStore | None = None,
) -> FastAPI:
    manifest = load_service_manifest(manifest_path)
    active = settings or Settings()
    active.assert_audit_safe()
    runtime = store or AuditAnchorStore(
        active.database_url,
        Ed25519Signer(active.audit_private_key_b64, key_id=active.audit_key_id),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        await runtime.initialize()
        try:
            yield
        finally:
            await runtime.close()

    app = FastAPI(title="Sheily independent audit custodian", version="0.3.0", lifespan=lifespan)

    def authorize(token: str | None) -> None:
        if token is None or not secrets.compare_digest(token, active.internal_service_token):
            raise HTTPException(status_code=401, detail="invalid service identity")

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"service": manifest.id, "status": "alive"}

    @app.get("/health/ready")
    async def ready() -> dict[str, object]:
        if not await runtime.health():
            raise HTTPException(status_code=503, detail="audit store unavailable")
        return {"service": manifest.id, "status": "ready", "key_id": runtime.signer.key_id}

    @app.post("/v1/anchors", response_model=AuditAnchor, status_code=201)
    async def create_anchor(
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> AuditAnchor:
        authorize(service_token)
        try:
            return await runtime.create_anchor()
        except AuditIntegrityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/anchors", response_model=list[AuditAnchor])
    async def list_anchors(
        limit: int = Query(default=100, ge=1, le=1000),
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> list[AuditAnchor]:
        authorize(service_token)
        return await runtime.list_anchors(limit)

    return app
