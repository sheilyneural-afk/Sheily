"""Descubrimiento verificable de proveedores cargados en cada proceso FastAPI."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute

from noosfera_core.manifest import ModuleProviderConfig, ServiceManifest


def _bound_routes(app: FastAPI) -> set[tuple[str, str]]:
    return {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in (route.methods or set())
    }


def _provider_payload(provider: ModuleProviderConfig, *, service_id: str) -> dict[str, object]:
    return {
        "id": provider.id,
        "service": service_id,
        "modules": provider.modules,
        "endpoint": provider.endpoint,
        "methods": provider.methods,
        "maturity": provider.maturity,
        "capabilities": provider.capabilities,
        "evidence": provider.evidence,
        "status": "loaded",
        "route_bound": True,
        "invocable": True,
    }


def install_runtime_module_registry(app: FastAPI, manifest: ServiceManifest) -> FastAPI:
    """Valida proveedores contra rutas reales y publica el inventario del proceso.

    El servicio falla al construirse si un manifiesto anuncia un proveedor cuya ruta
    o método no está cargado. Los módulos conceptuales sin proveedor siguen visibles
    como declarados, pero nunca se presentan como ejecutables.
    """

    bound = _bound_routes(app)
    seen_provider_ids: set[str] = set()
    for provider in manifest.providers:
        if provider.id in seen_provider_ids:
            raise RuntimeError(f"duplicate module provider id: {provider.id}")
        seen_provider_ids.add(provider.id)
        missing = [
            f"{method} {provider.endpoint}"
            for method in provider.methods
            if (provider.endpoint, method) not in bound
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"module provider {provider.id} has unbound route(s): {joined}")

    provider_payloads = [
        _provider_payload(provider, service_id=manifest.id) for provider in manifest.providers
    ]
    provided_modules = sorted(
        {module_id for provider in manifest.providers for module_id in provider.modules}
    )
    declared_modules = sorted(manifest.modules)
    unprovided_modules = sorted(set(declared_modules) - set(provided_modules))

    def snapshot() -> dict[str, Any]:
        return {
            "service": manifest.id,
            "version": manifest.version,
            "declared_modules": declared_modules,
            "declared_count": len(declared_modules),
            "provided_modules": provided_modules,
            "provided_count": len(provided_modules),
            "unprovided_modules": unprovided_modules,
            "providers": provider_payloads,
        }

    app.state.module_registry = snapshot

    @app.get("/v1/modules", include_in_schema=True)
    async def list_runtime_modules() -> dict[str, Any]:
        return snapshot()

    @app.get("/v1/modules/{module_id}", include_in_schema=True)
    async def get_runtime_module(module_id: str) -> dict[str, object]:
        matching = [
            payload
            for provider, payload in zip(manifest.providers, provider_payloads, strict=True)
            if module_id in provider.modules
        ]
        if not matching:
            if module_id in declared_modules:
                return {
                    "module_id": module_id,
                    "service": manifest.id,
                    "status": "declared",
                    "invocable": False,
                    "providers": [],
                }
            raise HTTPException(status_code=404, detail="module is not declared or provided here")
        return {
            "module_id": module_id,
            "service": manifest.id,
            "status": "loaded",
            "invocable": True,
            "providers": matching,
        }

    return app
