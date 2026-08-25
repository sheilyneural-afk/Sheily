"""Host HTTP de referencia para los catorce dominios."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from noosfera_core.config import Settings
from noosfera_core.manifest import ServiceManifest, load_service_manifest
from noosfera_core.module_registry import install_runtime_module_registry


def create_app(manifest_path: str | Path) -> FastAPI:
    manifest: ServiceManifest = load_service_manifest(manifest_path)
    settings = Settings()
    settings.assert_production_safe()
    app = FastAPI(title=manifest.id, version=manifest.version)

    @app.get(manifest.health.liveness)
    async def liveness() -> dict[str, object]:
        return {
            "service": manifest.id,
            "version": manifest.version,
            "status": "alive",
            "declared_modules": manifest.modules,
        }

    @app.get(manifest.health.readiness)
    async def readiness() -> dict[str, object]:
        return {
            "service": manifest.id,
            "node": settings.node_id,
            "status": "ready-reference-mode",
            "deny_by_default": manifest.deny_by_default,
        }

    @app.get("/v1/manifest")
    async def service_manifest() -> dict[str, object]:
        return manifest.model_dump(mode="json")

    @app.post("/v1/modules/{module_id}/invoke")
    async def invoke_unimplemented_module(module_id: str) -> None:
        if module_id not in manifest.modules:
            raise HTTPException(status_code=404, detail="module is not declared here")
        raise HTTPException(
            status_code=501,
            detail="logical module has a contract but no capability provider in reference mode",
        )

    return install_runtime_module_registry(app, manifest)
