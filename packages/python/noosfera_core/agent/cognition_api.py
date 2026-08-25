"""API del núcleo cognitivo, sin acceso a claves de Agency o Governance."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from noosfera_core.agent.cognition import CognitionRejected, CognitiveCycleStore, CognitiveKernel
from noosfera_core.agent.models import Belief, CognitiveCycle
from noosfera_core.agent.self_model import (
    RegistrySelfModel,
    SelfModelSnapshot,
    parse_runtime_registry_urls,
)
from noosfera_core.config import Settings
from noosfera_core.manifest import load_service_manifest
from noosfera_core.module_registry import install_runtime_module_registry


class CycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str
    user_id: str
    prompt: str = Field(min_length=1, max_length=20_000)
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    remember: bool = False


def create_cognition_app(
    manifest_path: str | Path,
    *,
    settings: Settings | None = None,
    kernel: CognitiveKernel | None = None,
    store: CognitiveCycleStore | None = None,
) -> FastAPI:
    manifest = load_service_manifest(manifest_path)
    active = settings or Settings()
    if kernel is None:
        self_model = RegistrySelfModel(
            registry_path=active.self_model_registry_path,
            node_id=active.node_id,
            current_manifest=manifest,
            service_urls=parse_runtime_registry_urls(active.runtime_registry_urls),
            timeout_seconds=active.runtime_registry_timeout_seconds,
            cache_seconds=active.self_model_cache_seconds,
        )
        runtime = CognitiveKernel(self_model=self_model)
    else:
        runtime = kernel
    cycles = store or CognitiveCycleStore(active.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        await cycles.initialize()
        try:
            yield
        finally:
            await cycles.close()

    app = FastAPI(title="Sheily cognitive kernel", version="0.3.0", lifespan=lifespan)

    def authorize(token: str | None) -> None:
        if token is None or not secrets.compare_digest(token, active.internal_service_token):
            raise HTTPException(status_code=401, detail="invalid service identity")

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"service": manifest.id, "status": "alive"}

    @app.get("/health/ready")
    async def ready() -> dict[str, object]:
        return {
            "service": manifest.id,
            "status": "ready" if await cycles.health() else "not-ready",
            "planner": runtime.name,
        }

    @app.post("/v1/cycles", response_model=CognitiveCycle, status_code=201)
    async def deliberate(
        request: CycleRequest,
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> CognitiveCycle:
        authorize(service_token)
        try:
            cycle = await runtime.deliberate(**request.model_dump())
            await cycles.save(cycle)
            return cycle
        except CognitionRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/cycles/{cycle_id}", response_model=CognitiveCycle)
    async def get_cycle(
        cycle_id: str,
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> CognitiveCycle:
        authorize(service_token)
        cycle = await cycles.get(cycle_id)
        if cycle is None:
            raise HTTPException(status_code=404, detail="cycle not found")
        return cycle

    @app.get("/v1/beliefs/{user_id}", response_model=list[Belief])
    async def list_beliefs(
        user_id: str,
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
    ) -> list[Belief]:
        authorize(service_token)
        return await cycles.list_beliefs(user_id)

    @app.get("/v1/self-model", response_model=SelfModelSnapshot)
    async def inspect_self(
        service_token: str | None = Header(default=None, alias="X-Noosfera-Service-Token"),
        force_refresh: bool = Query(default=False),
    ) -> SelfModelSnapshot:
        authorize(service_token)
        return await runtime.inspect_self(force_refresh=force_refresh)

    installed = install_runtime_module_registry(app, manifest)
    if isinstance(runtime.self_model_source, RegistrySelfModel):
        runtime.self_model_source.bind_local_snapshot(installed.state.module_registry)
    return installed
