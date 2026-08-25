"""Núcleo cognitivo explícito: estado, metas, frontera, críticos y plan causal."""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from noosfera_core.agent.models import (
    Belief,
    CandidateAction,
    CognitiveCycle,
    DriveState,
    Goal,
    MissionPlan,
    PlanStep,
    new_id,
    utc_now,
)
from noosfera_core.agent.self_model import RegistrySelfModel, SelfModelGateway, SelfModelSnapshot
from noosfera_core.hashing import canonical_hash


class CognitionRejected(RuntimeError):
    pass


class CognitionGateway(Protocol):
    name: str

    async def health(self) -> bool: ...

    async def deliberate(
        self,
        *,
        mission_id: str,
        user_id: str,
        prompt: str,
        document_ids: list[str],
        remember: bool,
    ) -> CognitiveCycle: ...

    async def inspect_self(self, *, force_refresh: bool = False) -> SelfModelSnapshot: ...


class CognitiveKernel:
    """Planificador interpretable que no delega metas ni autoridad al LLM."""

    name = "causal-cognitive-kernel-v1"

    def __init__(self, self_model: SelfModelGateway | None = None) -> None:
        self.self_model_source = self_model or RegistrySelfModel(
            registry_path="registry",
            node_id="node-in-process",
        )

    async def health(self) -> bool:
        return True

    async def inspect_self(self, *, force_refresh: bool = False) -> SelfModelSnapshot:
        return await self.self_model_source.snapshot(force_refresh=force_refresh)

    async def deliberate(
        self,
        *,
        mission_id: str,
        user_id: str,
        prompt: str,
        document_ids: list[str],
        remember: bool,
    ) -> CognitiveCycle:
        normalized = " ".join(prompt.split())
        if not normalized:
            raise CognitionRejected("empty observation")
        cycle_id = new_id("cognitive-cycle")
        has_documents = bool(document_ids)
        drives = DriveState(
            safety=0.15,
            privacy=0.55 if has_documents or remember else 0.1,
            epistemic_uncertainty=0.3 if has_documents else 0.2,
            task_completion=0.8,
            resource_pressure=0.1,
        )
        beliefs = [
            Belief(
                proposition="la persona solicitó explícitamente un resultado informativo acotado",
                confidence=1.0,
                provenance=[f"urn:noosfera:mission:{mission_id}:prompt"],
            ),
            Belief(
                proposition=(
                    "hay documentos autorizados adjuntos"
                    if has_documents
                    else "no hay evidencia documental adjunta"
                ),
                confidence=1.0,
                provenance=document_ids,
            ),
            Belief(
                proposition="este runtime prohíbe todos los efectos externos",
                confidence=1.0,
                provenance=["urn:noosfera:constitution:deny-by-default"],
            ),
        ]
        goals = [
            Goal(
                id=new_id("goal"),
                description="Satisfacer la petición informativa explícita de la persona",
                priority=0.9,
                source="user",
            ),
            Goal(
                id=new_id("goal"),
                description="Preservar el control, la privacidad y la reversibilidad",
                priority=1.0,
                source="constitutional",
            ),
            Goal(
                id=new_id("goal"),
                description="Mostrar la incertidumbre y la procedencia de la evidencia",
                priority=0.8,
                source="homeostasis",
            ),
        ]
        answer_candidate = CandidateAction(
            tool="conversation.answer",
            utility=0.82 if not has_documents else 0.35,
            risk=0.02,
            evidence_sufficiency=0.8 if not has_documents else 0.25,
            allowed=not has_documents,
            reasons=[
                "resultado puramente informativo",
                "no requiere acceder a documentos"
                if not has_documents
                else "ignora la evidencia adjunta",
            ],
        )
        report_candidate = CandidateAction(
            tool="document.report",
            utility=0.9 if has_documents else 0.1,
            risk=0.18 if has_documents else 0.0,
            evidence_sufficiency=0.95 if has_documents else 0.0,
            allowed=has_documents,
            reasons=[
                "conserva la procedencia de las fuentes",
                "requiere consentimiento explícito porque procesa documentos privados",
            ],
        )
        abstain_candidate = CandidateAction(
            tool="abstain",
            utility=0.05,
            risk=0.0,
            evidence_sufficiency=1.0,
            allowed=True,
            reasons=["alternativa segura si los críticos rechazan todas las acciones útiles"],
        )
        frontier = [answer_candidate, report_candidate, abstain_candidate]
        selected = report_candidate if has_documents else answer_candidate
        if not selected.allowed:
            raise CognitionRejected("no productive action passed the cognitive critics")
        if has_documents:
            plan = MissionPlan(
                objective="Analizar solo los documentos autorizados y crear un informe trazable",
                tool="document.report",
                operation="generate",
                resource="urn:noosfera:tool:document-report",
                steps=[
                    PlanStep(index=1, description="Cargar únicamente la evidencia autorizada"),
                    PlanStep(index=2, description="Extraer afirmaciones conservando su fuente"),
                    PlanStep(index=3, description="Redactar el informe solicitado"),
                    PlanStep(index=4, description="Verificar fuentes y límites del resultado"),
                ],
                success_criteria=[
                    "Toda afirmación basada en evidencia identifica una fuente autorizada",
                    "El informe no está vacío y respeta los límites de recursos",
                ],
                risk_factors=[
                    "Procesamiento de documentos privados",
                    "Incertidumbre de la síntesis del modelo",
                ],
                requires_documents=True,
                cognitive_cycle_id=cycle_id,
            )
        else:
            plan = MissionPlan(
                objective="Producir una respuesta local acotada a la petición",
                tool="conversation.answer",
                operation="answer",
                resource="urn:noosfera:tool:conversation-answer",
                steps=[
                    PlanStep(index=1, description="Interpretar la petición explícita"),
                    PlanStep(index=2, description="Generar una respuesta informativa acotada"),
                    PlanStep(index=3, description="Comprobar coherencia, incertidumbre y límites"),
                ],
                success_criteria=[
                    "La respuesta no está vacía",
                    "No se produce ningún efecto externo",
                ],
                risk_factors=["Incertidumbre de la síntesis del modelo"],
                requires_documents=False,
                cognitive_cycle_id=cycle_id,
            )
        return CognitiveCycle(
            id=cycle_id,
            mission_id=mission_id,
            user_id=user_id,
            observation_hash=canonical_hash(
                {"prompt": normalized, "document_ids": sorted(document_ids), "remember": remember}
            ),
            drives=drives,
            beliefs=beliefs,
            goals=goals,
            frontier=frontier,
            selected_tool=plan.tool,
            plan=plan,
            uncertainty=drives.epistemic_uncertainty,
            explanation=[
                "Una meta de la persona inició el ciclo; Sheily no inventó un mandato nuevo.",
                f"La frontera crítica seleccionó {plan.tool} entre acciones acotadas.",
                "Agency y Governance permanecen como autoridades posteriores independientes.",
            ],
            created_at=utc_now(),
        )


class RemoteCognitionClient:
    name = "remote-cognition-service"

    def __init__(self, base_url: str, *, service_token: str, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/health/ready")
                return response.is_success
        except httpx.HTTPError:
            return False

    async def deliberate(
        self,
        *,
        mission_id: str,
        user_id: str,
        prompt: str,
        document_ids: list[str],
        remember: bool,
    ) -> CognitiveCycle:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/v1/cycles",
                    headers={"X-Noosfera-Service-Token": self.service_token},
                    json={
                        "mission_id": mission_id,
                        "user_id": user_id,
                        "prompt": prompt,
                        "document_ids": document_ids,
                        "remember": remember,
                    },
                )
        except httpx.HTTPError as exc:
            raise CognitionRejected("cognition service is unavailable") from exc
        if response.status_code != 201:
            raise CognitionRejected(f"cognition service rejected cycle: {response.text[:500]}")
        return CognitiveCycle.model_validate(response.json())

    async def inspect_self(self, *, force_refresh: bool = False) -> SelfModelSnapshot:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url}/v1/self-model",
                    headers={"X-Noosfera-Service-Token": self.service_token},
                    params={"force_refresh": force_refresh},
                )
        except httpx.HTTPError as exc:
            raise CognitionRejected("cognition self-model is unavailable") from exc
        if response.status_code != 200:
            raise CognitionRejected(
                f"cognition service rejected self-model read: {response.text[:500]}"
            )
        return SelfModelSnapshot.model_validate(response.json())


class CognitiveCycleStore:
    """Repositorio propio del dominio cognitivo."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url
        self._pool: Any = None
        self._memory: dict[str, CognitiveCycle] = {}
        self._beliefs: dict[str, dict[str, Belief]] = {}

    async def initialize(self) -> None:
        if self.database_url is None:
            return
        import asyncpg  # type: ignore[import-untyped]

        self._pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        await self._pool.execute(
            """CREATE TABLE IF NOT EXISTS cognitive_cycles (
                 id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, user_id TEXT NOT NULL,
                 observation_hash CHAR(64) NOT NULL, payload JSONB NOT NULL,
                 created_at TIMESTAMPTZ NOT NULL
               );
               CREATE INDEX IF NOT EXISTS idx_cognitive_cycles_mission
                 ON cognitive_cycles(mission_id, created_at DESC);
               CREATE TABLE IF NOT EXISTS cognitive_beliefs (
                 user_id TEXT NOT NULL, proposition_hash CHAR(64) NOT NULL,
                 belief JSONB NOT NULL, source_cycle_id TEXT NOT NULL,
                 first_observed_at TIMESTAMPTZ NOT NULL,
                 last_observed_at TIMESTAMPTZ NOT NULL,
                 superseded_at TIMESTAMPTZ,
                 PRIMARY KEY(user_id, proposition_hash)
               );
               CREATE INDEX IF NOT EXISTS idx_cognitive_beliefs_active
                 ON cognitive_beliefs(user_id,last_observed_at DESC)
                 WHERE superseded_at IS NULL;"""
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

    async def save(self, cycle: CognitiveCycle) -> None:
        if self._pool is None:
            self._memory[cycle.id] = cycle
            values = self._beliefs.setdefault(cycle.user_id, {})
            for belief in cycle.beliefs:
                values[canonical_hash(belief.proposition)] = belief
            return
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """INSERT INTO cognitive_cycles
                     (id,mission_id,user_id,observation_hash,payload,created_at)
                   VALUES($1,$2,$3,$4,$5::jsonb,$6)""",
                cycle.id,
                cycle.mission_id,
                cycle.user_id,
                cycle.observation_hash,
                cycle.model_dump_json(),
                cycle.created_at,
            )
            for belief in cycle.beliefs:
                await connection.execute(
                    """INSERT INTO cognitive_beliefs
                         (user_id,proposition_hash,belief,source_cycle_id,
                          first_observed_at,last_observed_at)
                       VALUES($1,$2,$3::jsonb,$4,$5,$5)
                       ON CONFLICT(user_id,proposition_hash) DO UPDATE
                         SET belief=EXCLUDED.belief,
                             source_cycle_id=EXCLUDED.source_cycle_id,
                             last_observed_at=EXCLUDED.last_observed_at,
                             superseded_at=NULL""",
                    cycle.user_id,
                    canonical_hash(belief.proposition),
                    belief.model_dump_json(),
                    cycle.id,
                    cycle.created_at,
                )

    async def get(self, cycle_id: str) -> CognitiveCycle | None:
        if self._pool is None:
            return self._memory.get(cycle_id)
        row = await self._pool.fetchrow(
            "SELECT payload FROM cognitive_cycles WHERE id=$1", cycle_id
        )
        if not row:
            return None
        payload = row["payload"]
        return CognitiveCycle.model_validate(
            json.loads(payload) if isinstance(payload, str) else payload
        )

    async def list_beliefs(self, user_id: str, limit: int = 100) -> list[Belief]:
        if self._pool is None:
            return list(self._beliefs.get(user_id, {}).values())[:limit]
        rows = await self._pool.fetch(
            """SELECT belief FROM cognitive_beliefs
               WHERE user_id=$1 AND superseded_at IS NULL
               ORDER BY last_observed_at DESC LIMIT $2""",
            user_id,
            limit,
        )
        result: list[Belief] = []
        for row in rows:
            payload = row["belief"]
            result.append(
                Belief.model_validate(json.loads(payload) if isinstance(payload, str) else payload)
            )
        return result
