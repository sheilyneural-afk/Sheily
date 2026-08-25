"""Proveedor local de modelo; nunca conmuta silenciosamente a la nube."""

from __future__ import annotations

import json
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from noosfera_core.agent.models import (
    DocumentRecord,
    EvidenceReference,
    MissionPlan,
    ModelOutput,
    PlanStep,
)


class ModelUnavailable(RuntimeError):
    pass


class AgentModel(Protocol):
    provider_name: str
    model_name: str

    async def health(self) -> bool: ...

    async def plan(self, prompt: str, *, has_documents: bool) -> MissionPlan: ...

    async def respond(
        self, prompt: str, *, documents: list[DocumentRecord], history: list[dict[str, str]]
    ) -> ModelOutput: ...


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
        allow_remote: bool = False,
    ) -> None:
        assert_local_endpoint(base_url, allow_remote)
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.max_input_chars = max_input_chars
        self.context_tokens = context_tokens
        self.output_tokens = output_tokens

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
        return MissionPlan.model_validate(raw)

    async def respond(
        self, prompt: str, *, documents: list[DocumentRecord], history: list[dict[str, str]]
    ) -> ModelOutput:
        document_payload = [
            {"id": item.id, "name": item.name, "content": item.text} for item in documents
        ]
        system = (
            "You are Sheily running locally. Answer only from the supplied conversation and "
            "documents. Cite a document only with its exact id. State uncertainty. Return only "
            "JSON matching the schema. Do not claim to have used external sources or tools."
        )
        user = json.dumps(
            {"request": prompt, "history": history[-12:], "documents": document_payload},
            ensure_ascii=False,
        )
        raw = await self._structured(
            system=system, user=user, schema=ModelOutput.model_json_schema()
        )
        return ModelOutput.model_validate(raw)


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
        self, prompt: str, *, documents: list[DocumentRecord], history: list[dict[str, str]]
    ) -> ModelOutput:
        del history
        if documents:
            sections = [
                f"## {document.name}\n\n{document.text[:500].strip()}" for document in documents
            ]
            return ModelOutput(
                answer=(
                    f"# Informe de referencia\n\nSolicitud: {prompt}\n\n"
                    + "\n\n".join(sections)
                    + (
                        "\n\n> Resultado determinista de pruebas; configure Ollama "
                        "para análisis real."
                    )
                ),
                citations=[
                    EvidenceReference(document_id=document.id, label=document.name)
                    for document in documents
                ],
            )
        return ModelOutput(
            answer=(
                f"Respuesta determinista a: {prompt}\n\n"
                "Configure un modelo local para obtener una respuesta generativa real."
            )
        )
