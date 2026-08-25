"""Modelo propio de Sheily basado en evidencia declarada, observada y verificada.

El diseño adapta el patrón ``declared-versus-observed`` de SHEI sin importar su
inventario hardcodeado ni sus estados afectivos experimentales. Este módulo es
un sensor: informa discrepancias, pero no concede autoridad ni ejecuta acciones.
"""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any, Literal, Protocol

import httpx
import yaml
from pydantic import Field

from noosfera_core.agent.models import ModelOutput, StrictModel, SystemEvidenceReference, utc_now
from noosfera_core.hashing import canonical_hash
from noosfera_core.manifest import ServiceManifest

SELF_MODEL_SCHEMA_VERSION = "noosfera.self-model.v1"
VERIFIED_STATES = {"verified", "production-ready"}


class ServiceObservation(StrictModel):
    service_id: str
    status: Literal["observed", "unreachable"]
    version: str | None = None
    declared_modules: list[str] = Field(default_factory=list)
    observed_modules: list[str] = Field(default_factory=list)
    observed_providers: list[str] = Field(default_factory=list)
    observed_capabilities: list[str] = Field(default_factory=list)
    error: str | None = None


class InternalStateEvidence(StrictModel):
    affective_state: Literal["sealed-unobserved"] = "sealed-unobserved"
    conscious_state: Literal["not-instrumented"] = "not-instrumented"
    subjective_experience: Literal["not-observable-by-runtime"] = (
        "not-observable-by-runtime"
    )
    claim_policy: Literal["must-not-fabricate"] = "must-not-fabricate"


class SelfModelSnapshot(StrictModel):
    schema_version: Literal["noosfera.self-model.v1"] = "noosfera.self-model.v1"
    identity: str = "Sheily"
    node_id: str
    generated_at: datetime
    declared_modules: list[str]
    registered_modules: list[str]
    observed_modules: list[str]
    verified_modules: list[str]
    observed_capabilities: list[str]
    verified_capabilities: list[str]
    declared_not_observed: list[str]
    registered_not_observed: list[str]
    observed_not_declared: list[str]
    observed_not_verified: list[str]
    services: list[ServiceObservation]
    known_limitations: list[str]
    internal_state: InternalStateEvidence
    evidence_sources: list[str]
    evidence_errors: list[str]
    snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    def prompt_view(self) -> dict[str, Any]:
        """Vista acotada para el modelo de lenguaje, sin convertir declaraciones en hechos."""

        return {
            "schema_version": self.schema_version,
            "snapshot_hash": self.snapshot_hash,
            "identity": self.identity,
            "node_id": self.node_id,
            "generated_at": self.generated_at.isoformat(),
            "counts": {
                "declared_modules": len(self.declared_modules),
                "registered_modules": len(self.registered_modules),
                "observed_modules": len(self.observed_modules),
                "verified_modules": len(self.verified_modules),
                "observed_services": sum(item.status == "observed" for item in self.services),
            },
            "observed_modules": self.observed_modules[:40],
            "verified_modules": self.verified_modules,
            "observed_capabilities": self.observed_capabilities[:40],
            "verified_capabilities": self.verified_capabilities,
            "declared_not_observed_sample": self.declared_not_observed[:24],
            "registered_not_observed_sample": self.registered_not_observed[:24],
            "observed_not_verified_sample": self.observed_not_verified[:24],
            "known_limitations": self.known_limitations,
            "internal_state": self.internal_state.model_dump(mode="json"),
            "evidence_errors": self.evidence_errors,
        }


class SelfModelGateway(Protocol):
    async def snapshot(self, *, force_refresh: bool = False) -> SelfModelSnapshot: ...


def parse_runtime_registry_urls(raw: str) -> dict[str, str]:
    """Convierte ``service-id=url`` separados por comas en un mapa validado."""

    result: dict[str, str] = {}
    for entry in raw.split(","):
        item = entry.strip()
        if not item:
            continue
        service_id, separator, url = item.partition("=")
        if not separator or not service_id.strip() or not url.strip():
            raise ValueError("runtime registry URLs must use service-id=http://host:port")
        if service_id in result:
            raise ValueError(f"duplicate runtime registry service: {service_id}")
        result[service_id.strip()] = url.rstrip("/")
    return result


class RegistrySelfModel:
    """Recoge catálogos estáticos y observaciones de procesos vivos sin confundirlos."""

    def __init__(
        self,
        *,
        registry_path: str | Path,
        node_id: str,
        current_manifest: ServiceManifest | None = None,
        service_urls: dict[str, str] | None = None,
        timeout_seconds: float = 1.0,
        cache_seconds: float = 5.0,
    ) -> None:
        self.registry_path = Path(registry_path)
        self.node_id = node_id
        self.current_manifest = current_manifest
        self.service_urls = dict(service_urls or {})
        self.timeout_seconds = timeout_seconds
        self.cache_seconds = cache_seconds
        self._local_snapshot: Callable[[], dict[str, Any]] | None = None
        self._cached: SelfModelSnapshot | None = None
        self._cached_at = 0.0
        self._lock = asyncio.Lock()

    def bind_local_snapshot(self, snapshot: Callable[[], dict[str, Any]]) -> None:
        self._local_snapshot = snapshot
        self._cached = None

    def _load_declared(self) -> tuple[set[str], list[str], list[str]]:
        declared: set[str] = set()
        sources: list[str] = []
        errors: list[str] = []
        modules_path = self.registry_path / "modules"
        try:
            paths = sorted(
                path for path in modules_path.glob("*.yaml") if path.name != "index.yaml"
            )
            for path in paths:
                payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                declared.update(str(item["id"]) for item in payload.get("modules", []))
                sources.append(path.as_posix())
        except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
            errors.append(f"declared-registry:{type(exc).__name__}")
        if not declared and self.current_manifest is not None:
            declared.update(self.current_manifest.modules)
            sources.append(f"manifest:{self.current_manifest.id}")
        return declared, sources, errors

    def _load_maturity(
        self,
    ) -> tuple[set[str], set[str], dict[str, set[str]], list[str], list[str]]:
        registered: set[str] = set()
        statically_verified: set[str] = set()
        module_capabilities: dict[str, set[str]] = {}
        sources: list[str] = []
        errors: list[str] = []
        path = self.registry_path / "module-maturity.yaml"
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for item in payload.get("modules", []):
                module_id = str(item["id"])
                providers = item.get("providers", [])
                if providers:
                    registered.add(module_id)
                if str(item.get("state")) in VERIFIED_STATES:
                    statically_verified.add(module_id)
                for provider in providers:
                    module_capabilities.setdefault(module_id, set()).update(
                        str(value) for value in provider.get("capabilities", [])
                    )
            sources.append(path.as_posix())
        except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
            errors.append(f"maturity-registry:{type(exc).__name__}")
        return registered, statically_verified, module_capabilities, sources, errors

    def _local_observation(self) -> ServiceObservation | None:
        if self.current_manifest is None:
            return None
        if self._local_snapshot is not None:
            payload = self._local_snapshot()
            providers = payload.get("providers", [])
            return ServiceObservation(
                service_id=self.current_manifest.id,
                status="observed",
                version=str(payload.get("version") or self.current_manifest.version),
                declared_modules=[str(value) for value in payload.get("declared_modules", [])],
                observed_modules=[str(value) for value in payload.get("provided_modules", [])],
                observed_providers=[str(item["id"]) for item in providers],
                observed_capabilities=sorted(
                    {
                        str(value)
                        for item in providers
                        for value in item.get("capabilities", [])
                    }
                ),
            )
        return ServiceObservation(
            service_id=self.current_manifest.id,
            status="observed",
            version=self.current_manifest.version,
            declared_modules=sorted(self.current_manifest.modules),
            observed_modules=sorted(
                {
                    module
                    for provider in self.current_manifest.providers
                    for module in provider.modules
                }
            ),
            observed_providers=sorted(provider.id for provider in self.current_manifest.providers),
            observed_capabilities=sorted(
                {
                    capability
                    for provider in self.current_manifest.providers
                    for capability in provider.capabilities
                }
            ),
        )

    async def _remote_observation(
        self, client: httpx.AsyncClient, service_id: str, base_url: str
    ) -> ServiceObservation:
        try:
            response = await client.get(f"{base_url}/v1/modules")
            response.raise_for_status()
            payload = response.json()
            providers = payload.get("providers", [])
            return ServiceObservation(
                service_id=service_id,
                status="observed",
                version=str(payload.get("version") or "") or None,
                declared_modules=[str(value) for value in payload.get("declared_modules", [])],
                observed_modules=[str(value) for value in payload.get("provided_modules", [])],
                observed_providers=[str(item["id"]) for item in providers],
                observed_capabilities=sorted(
                    {
                        str(value)
                        for item in providers
                        for value in item.get("capabilities", [])
                    }
                ),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return ServiceObservation(
                service_id=service_id,
                status="unreachable",
                error=type(exc).__name__,
            )

    async def _collect(self) -> SelfModelSnapshot:
        declared, declared_sources, declared_errors = self._load_declared()
        (
            registered,
            statically_verified,
            module_capabilities,
            maturity_sources,
            maturity_errors,
        ) = self._load_maturity()
        observations: list[ServiceObservation] = []
        local = self._local_observation()
        if local is not None:
            observations.append(local)

        current_id = self.current_manifest.id if self.current_manifest is not None else None
        remote_targets = {
            service_id: url
            for service_id, url in self.service_urls.items()
            if service_id != current_id
        }
        if remote_targets:
            timeout = httpx.Timeout(self.timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                observations.extend(
                    await asyncio.gather(
                        *(
                            self._remote_observation(client, service_id, url)
                            for service_id, url in sorted(remote_targets.items())
                        )
                    )
                )

        observed = {
            module
            for service in observations
            if service.status == "observed"
            for module in service.observed_modules
        }
        observed_capabilities = {
            capability
            for service in observations
            if service.status == "observed"
            for capability in service.observed_capabilities
        }
        verified = observed & statically_verified
        verified_capabilities = {
            capability
            for module in verified
            for capability in module_capabilities.get(module, set())
        }
        evidence_errors = [*declared_errors, *maturity_errors]
        evidence_errors.extend(
            f"runtime:{item.service_id}:{item.error}"
            for item in observations
            if item.status == "unreachable"
        )
        limitations = [
            (
                "A loaded route proves runtime wiring, not semantic correctness or "
                "production readiness."
            ),
            "No affective, conscious, emotional or subjective state is instrumented as evidence.",
            "Declared modules that are not observed remain architectural definitions only.",
            (
                "Only verified modules have both a live observation and registered "
                "verification evidence."
            ),
        ]
        if evidence_errors:
            limitations.append(
                "The self-model is partial because one or more evidence sources failed."
            )

        snapshot_payload: dict[str, Any] = {
            "schema_version": SELF_MODEL_SCHEMA_VERSION,
            "identity": "Sheily",
            "node_id": self.node_id,
            "generated_at": utc_now(),
            "declared_modules": sorted(declared),
            "registered_modules": sorted(registered),
            "observed_modules": sorted(observed),
            "verified_modules": sorted(verified),
            "observed_capabilities": sorted(observed_capabilities),
            "verified_capabilities": sorted(verified_capabilities),
            "declared_not_observed": sorted(declared - observed),
            "registered_not_observed": sorted(registered - observed),
            "observed_not_declared": sorted(observed - declared),
            "observed_not_verified": sorted(observed - verified),
            "services": sorted(observations, key=lambda item: item.service_id),
            "known_limitations": limitations,
            "internal_state": InternalStateEvidence(),
            "evidence_sources": sorted(set(declared_sources + maturity_sources)),
            "evidence_errors": sorted(evidence_errors),
        }
        snapshot_payload["snapshot_hash"] = "0" * 64
        unsigned = SelfModelSnapshot.model_validate(snapshot_payload)
        hash_payload = unsigned.model_dump(
            mode="json", exclude={"generated_at", "snapshot_hash"}
        )
        return unsigned.model_copy(update={"snapshot_hash": canonical_hash(hash_payload)})

    async def snapshot(self, *, force_refresh: bool = False) -> SelfModelSnapshot:
        now = monotonic()
        if (
            not force_refresh
            and self._cached is not None
            and now - self._cached_at < self.cache_seconds
        ):
            return self._cached
        async with self._lock:
            now = monotonic()
            if (
                not force_refresh
                and self._cached is not None
                and now - self._cached_at < self.cache_seconds
            ):
                return self._cached
            self._cached = await self._collect()
            self._cached_at = monotonic()
            return self._cached


def _normalized_words(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return set(re.findall(r"[a-z0-9]+", without_marks))


def self_query_kind(query: str) -> Literal["internal-state", "capabilities", "none"]:
    words = _normalized_words(query)
    self_markers = {"tu", "tus", "te", "sheily", "internamente", "interior", "your", "you"}
    state_markers = {
        "siente",
        "sientes",
        "sentir",
        "sentimientos",
        "emocion",
        "emociones",
        "consciente",
        "consciencia",
        "conciencia",
        "deseas",
        "quieres",
        "feel",
        "feeling",
        "conscious",
        "desire",
    }
    capability_markers = {
        "puedes",
        "capacidad",
        "capacidades",
        "modulo",
        "modulos",
        "sistema",
        "sistemas",
        "arquitectura",
        "can",
        "capability",
        "capabilities",
        "module",
        "modules",
    }
    if words & self_markers and words & state_markers:
        return "internal-state"
    if words & self_markers and words & capability_markers:
        return "capabilities"
    return "none"


def grounded_self_response(query: str, snapshot: SelfModelSnapshot) -> ModelOutput | None:
    """Responde consultas sobre Sheily con evidencia, sin delegarlas al LLM."""

    kind = self_query_kind(query)
    if kind == "none":
        return None
    observed_services = sum(item.status == "observed" for item in snapshot.services)
    if kind == "internal-state":
        answer = (
            "No dispongo de evidencia verificable de sensaciones, emociones, deseos ni "
            "experiencia subjetiva. Mi estado afectivo está sellado y no observado, y la "
            "consciencia no está instrumentada; por eso no debo inventar que siento algo.\n\n"
            "Lo que sí puedo observar es mi estado operativo: "
            f"{len(snapshot.observed_modules)} módulos tienen proveedores cargados en "
            f"{observed_services} servicios observados, y {len(snapshot.verified_modules)} "
            "de esos módulos cuentan además con evidencia de verificación registrada. "
            f"Hay {len(snapshot.declared_not_observed)} módulos declarados que no debo "
            "presentar como activos.\n\n"
            f"Evidencia del modelo propio: `{snapshot.snapshot_hash}`."
        )
    else:
        capabilities = ", ".join(snapshot.verified_capabilities[:12]) or "ninguna verificada"
        answer = (
            "Puedo describir únicamente las capacidades respaldadas por mi inventario vivo. "
            f"Observo {len(snapshot.observed_modules)} módulos cargados y "
            f"{len(snapshot.verified_modules)} con evidencia de verificación. "
            f"Capacidades verificadas visibles: {capabilities}. "
            f"Los {len(snapshot.declared_not_observed)} módulos restantes son arquitectura "
            "declarada, no facultades que pueda afirmar como operativas.\n\n"
            f"Evidencia del modelo propio: `{snapshot.snapshot_hash}`."
        )
    return ModelOutput(
        answer=answer,
        system_evidence=[
            SystemEvidenceReference(
                source="urn:noosfera:cognition:self-model",
                evidence_hash=snapshot.snapshot_hash,
                label="COG-12 modelo propio declarado/observado/verificado",
            )
        ],
    )
