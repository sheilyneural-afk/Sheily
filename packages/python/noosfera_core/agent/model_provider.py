"""Proveedor local de modelo; nunca conmuta silenciosamente a la nube."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from noosfera_core.agent.models import (
    DocumentClaim,
    DocumentContradiction,
    DocumentEvidenceContext,
    DocumentLimitation,
    DocumentRecord,
    EvidenceReference,
    MissionPlan,
    ModelDraft,
    PlanStep,
)
from noosfera_core.agent.self_model import SelfModelSnapshot


class ModelUnavailable(RuntimeError):
    pass


class _LanguageCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(pattern=r"^E[0-9]+$")
    source_ref: str = Field(pattern=r"^S[0-9]+$")
    block_ref: str = Field(pattern=r"^B[0-9]+$")
    relation: Literal["supports", "contradicts", "limits"] = "supports"


class _LanguageClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^C[0-9]+$")
    statement: str = Field(min_length=1)
    epistemic_status: Literal["source-communication", "inference", "hypothesis"]
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class _LanguageContradiction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=2, max_length=8)


class _LanguageLimitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)


class _LanguageDocumentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    citations: list[_LanguageCitation] = Field(min_length=1, max_length=8)
    claims: list[_LanguageClaim] = Field(min_length=1, max_length=5)
    contradictions: list[_LanguageContradiction] = Field(default_factory=list, max_length=4)
    limitations: list[_LanguageLimitation] = Field(default_factory=list, max_length=6)
    unknowns: list[str] = Field(default_factory=list, max_length=6)
    assumptions: list[str] = Field(default_factory=list, max_length=6)


class AgentModel(Protocol):
    provider_name: str
    model_name: str

    async def health(self) -> bool: ...

    async def plan(self, prompt: str, *, has_documents: bool) -> MissionPlan: ...

    async def respond(
        self,
        prompt: str,
        *,
        documents: list[DocumentRecord],
        document_context: DocumentEvidenceContext | None,
        history: list[dict[str, str]],
        self_model: SelfModelSnapshot,
    ) -> ModelDraft: ...


def assert_local_endpoint(base_url: str, allow_remote: bool) -> None:
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    local_hosts = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"}
    if not allow_remote and host not in local_hosts:
        raise ValueError("remote model endpoint is forbidden unless explicitly enabled")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("model endpoint must use HTTP or HTTPS")


class OllamaModel:
    provider_name = "ollama-local"

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        timeout_seconds: float,
        max_input_chars: int,
        context_tokens: int,
        output_tokens: int,
        max_concurrency: int = 1,
        allow_remote: bool = False,
    ) -> None:
        assert_local_endpoint(base_url, allow_remote)
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.max_input_chars = max_input_chars
        self.context_tokens = context_tokens
        self.output_tokens = output_tokens
        self._inference_slots = asyncio.Semaphore(max_concurrency)

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.is_success
        except httpx.HTTPError:
            return False

    async def _structured(
        self, *, system: str, user: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        if len(user) > self.max_input_chars:
            raise ValueError("model input exceeds configured limit")
        request = {
            "model": self.model_name,
            "stream": False,
            "format": schema,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": 0.1,
                "num_ctx": self.context_tokens,
                "num_predict": self.output_tokens,
            },
        }
        try:
            async with self._inference_slots:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(f"{self.base_url}/api/chat", json=request)
                    response.raise_for_status()
            content = response.json()["message"]["content"]
            value = json.loads(content)
            if not isinstance(value, dict):
                raise ValueError("model returned a non-object JSON value")
            return value
        except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ModelUnavailable(
                "local Ollama model failed to produce structured output"
            ) from exc

    async def plan(self, prompt: str, *, has_documents: bool) -> MissionPlan:
        system = (
            "You are the planning component of Sheily. Return only JSON matching the schema. "
            "You may choose only conversation.answer or document.report. Never propose shell, "
            "filesystem, network, money, messaging, devices, code execution, or external actions."
        )
        user = json.dumps({"request": prompt, "documents_attached": has_documents})
        raw = await self._structured(
            system=system, user=user, schema=MissionPlan.model_json_schema()
        )
        # The model may describe the objective and steps, but it never selects its
        # own authority boundary. Bind the only permitted tool tuple to observed
        # document scope before validating the signed-plan contract.
        if has_documents:
            raw.update(
                {
                    "tool": "document.report",
                    "operation": "generate",
                    "resource": "urn:noosfera:tool:document-report",
                    "requires_documents": True,
                }
            )
        else:
            raw.update(
                {
                    "tool": "conversation.answer",
                    "operation": "answer",
                    "resource": "urn:noosfera:tool:conversation-answer",
                    "requires_documents": False,
                }
            )
        return MissionPlan.model_validate(raw)

    async def respond(
        self,
        prompt: str,
        *,
        documents: list[DocumentRecord],
        document_context: DocumentEvidenceContext | None,
        history: list[dict[str, str]],
        self_model: SelfModelSnapshot,
    ) -> ModelDraft:
        document_payload = None
        source_aliases: dict[str, Any] = {}
        block_aliases: dict[str, Any] = {}
        block_sources: dict[str, str] = {}
        if document_context is not None:
            source_aliases = {
                f"S{index}": source
                for index, source in enumerate(document_context.source_versions, start=1)
            }
            source_ref_by_id = {
                source.document_id: alias for alias, source in source_aliases.items()
            }
            block_aliases = {
                f"B{index}": block for index, block in enumerate(document_context.blocks, start=1)
            }
            block_sources = {
                alias: source_ref_by_id[block.document_id] for alias, block in block_aliases.items()
            }
            document_payload = {
                "sources": [
                    {
                        "source_ref": alias,
                        "label": source.label,
                    }
                    for alias, source in source_aliases.items()
                ],
                "blocks": [
                    {
                        "block_ref": alias,
                        "source_ref": block_sources[alias],
                        "kind": block.kind,
                        "page_number": block.page_number,
                        "section_path": block.section_path,
                        "critical": block.critical,
                        "text": block.text,
                    }
                    for alias, block in block_aliases.items()
                ],
                "missing_artifacts": document_context.missing_artifacts,
                "selection_method": document_context.selection_method,
            }
        system = (
            "You are Sheily running locally. Answer only from the supplied conversation and "
            "addressable document blocks. Return only JSON matching the schema. For every "
            "document claim, select one or more evidence blocks and use only the supplied short "
            "source_ref and block_ref aliases. Do not copy quote text: Sheily resolves each alias "
            "to its immutable source block outside the model. Produce at most five concise claims "
            "and eight "
            "citations. evidence_id and claim id must be unique labels such as E1 and C1. "
            "A source describes what its author communicates; it is not "
            "a direct observation by you. Preserve warnings, limitations, contradictions, missing "
            "artifacts and uncertainty. Never invent a citation. The answer is "
            "only a draft: an independent service will ignore unsupported prose and verify claims. "
            "Do not claim to have used external sources or tools. "
            "You receive no observed or sealed affective, conscious, emotional or subjective "
            "state. Therefore never claim that you feel, experience, desire or are conscious. "
            "Never turn a declared or loaded capability into a verified capability."
        )
        user = json.dumps(
            {
                "request": prompt,
                "history": history[-12:],
                "documents": document_payload,
                "runtime_evidence": {
                    "self_model_snapshot_hash": self_model.snapshot_hash,
                    "affective_or_subjective_state_observed": False,
                },
            },
            ensure_ascii=False,
        )
        schema = (
            _LanguageDocumentDraft.model_json_schema()
            if document_context is not None
            else ModelDraft.model_json_schema()
        )
        raw = await self._structured(system=system, user=user, schema=schema)
        if document_context is None:
            return ModelDraft.model_validate(raw)
        language = _LanguageDocumentDraft.model_validate(raw)
        citations: list[EvidenceReference] = []
        for citation in language.citations:
            source = source_aliases.get(citation.source_ref)
            block = block_aliases.get(citation.block_ref)
            if (
                source is None
                or block is None
                or block_sources.get(citation.block_ref) != citation.source_ref
            ):
                raise ModelUnavailable("local model referenced an unknown evidence alias")
            citations.append(
                EvidenceReference(
                    evidence_id=citation.evidence_id,
                    document_id=source.document_id,
                    version_id=source.version_id,
                    block_id=block.id,
                    label=source.label,
                    quote=block.text,
                    page_number=block.page_number,
                    section_path=block.section_path,
                    relation=citation.relation,
                )
            )
        return ModelDraft(
            answer=language.summary,
            citations=citations,
            claims=[DocumentClaim.model_validate(item.model_dump()) for item in language.claims],
            contradictions=[
                DocumentContradiction.model_validate(item.model_dump())
                for item in language.contradictions
            ],
            limitations=[
                DocumentLimitation(**item.model_dump(), system_detected=False)
                for item in language.limitations
            ],
            unknowns=language.unknowns,
            assumptions=language.assumptions,
        )


class DeterministicLocalModel:
    """Proveedor explícito de pruebas; no se presenta como un LLM."""

    provider_name = "deterministic-test"
    model_name = "deterministic-reference"

    async def health(self) -> bool:
        return True

    async def plan(self, prompt: str, *, has_documents: bool) -> MissionPlan:
        del prompt
        if has_documents:
            return MissionPlan(
                objective="Analizar los documentos autorizados y crear un informe trazable",
                tool="document.report",
                operation="generate",
                resource="urn:noosfera:tool:document-report",
                steps=[
                    PlanStep(index=1, description="Leer documentos autorizados"),
                    PlanStep(index=2, description="Extraer hechos y procedencia"),
                    PlanStep(index=3, description="Generar y verificar el informe"),
                ],
                success_criteria=["Informe no vacío", "Fuentes identificadas"],
                risk_factors=["Procesamiento de documentos privados"],
                requires_documents=True,
            )
        return MissionPlan(
            objective="Responder localmente a la petición sin acciones externas",
            tool="conversation.answer",
            operation="answer",
            resource="urn:noosfera:tool:conversation-answer",
            steps=[PlanStep(index=1, description="Generar una respuesta local")],
            success_criteria=["Respuesta no vacía"],
            requires_documents=False,
        )

    async def respond(
        self,
        prompt: str,
        *,
        documents: list[DocumentRecord],
        document_context: DocumentEvidenceContext | None,
        history: list[dict[str, str]],
        self_model: SelfModelSnapshot,
    ) -> ModelDraft:
        del history, self_model
        if documents:
            if document_context is None:
                raise ValueError("document analysis requires structured evidence context")
            citations: list[EvidenceReference] = []
            claims: list[DocumentClaim] = []
            sources = {item.document_id: item for item in document_context.source_versions}
            for index, document in enumerate(documents, start=1):
                block = next(
                    item for item in document_context.blocks if item.document_id == document.id
                )
                evidence_id = f"E{index}"
                quote = block.text[:500]
                citations.append(
                    EvidenceReference(
                        evidence_id=evidence_id,
                        document_id=document.id,
                        version_id=document.version_id,
                        block_id=block.id,
                        label=sources[document.id].label,
                        quote=quote,
                        page_number=block.page_number,
                        section_path=block.section_path,
                    )
                )
                claims.append(
                    DocumentClaim(
                        id=f"C{index}",
                        statement=quote,
                        epistemic_status="source-communication",
                        confidence=1.0,
                        evidence_ids=[evidence_id],
                    )
                )
            return ModelDraft(
                answer=f"Borrador determinista para: {prompt}",
                citations=citations,
                claims=claims,
            )
        return ModelDraft(
            answer=(
                f"Respuesta determinista a: {prompt}\n\n"
                "Configure un modelo local para obtener una respuesta generativa real."
            )
        )
