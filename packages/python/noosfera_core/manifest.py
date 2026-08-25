"""Carga y validación de manifiestos de servicio."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class HealthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    liveness: str
    readiness: str


class ModuleProviderConfig(BaseModel):
    """Proveedor explícito que debe corresponder a una ruta cargada en el proceso."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9.-]+$")
    modules: list[str] = Field(min_length=1)
    endpoint: str = Field(pattern=r"^/")
    methods: list[Literal["GET", "POST", "PUT", "PATCH", "DELETE"]] = Field(min_length=1)
    maturity: Literal["implemented", "integrated", "verified", "production-ready"]
    capabilities: list[str] = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)


class ServiceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9-]+-service$")
    family: str = Field(pattern=r"^[A-Z]{3}$")
    version: str
    runtime: str
    target_runtime: str | None = None
    modules: list[str] = Field(min_length=1)
    providers: list[ModuleProviderConfig] = Field(default_factory=list)
    inbound_buses: list[str]
    outbound_buses: list[str]
    data_stores: list[str]
    health: HealthConfig
    slo: str
    runbook: str
    owner: str
    deny_by_default: bool = True


def load_service_manifest(path: str | Path) -> ServiceManifest:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ServiceManifest.model_validate(raw)
