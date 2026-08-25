"""Verificador independiente de informes: el LLM no puede autodeclararse verificado."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import httpx

from noosfera_core.agent.crypto import Ed25519Signer
from noosfera_core.agent.models import (
    CoverageReport,
    DocumentBlock,
    DocumentClaim,
    DocumentContradiction,
    DocumentLimitation,
    DocumentVerificationInput,
    DocumentVerificationReport,
    EvidenceBundle,
    EvidenceReference,
    ModelOutput,
    new_id,
    utc_now,
)
from noosfera_core.hashing import canonical_hash

DOCUMENT_VERIFICATION_DOMAIN = "noosfera.audit.document-verification.v1"
WORD = re.compile(r"[\wáéíóúüñ]{3,}", re.IGNORECASE)
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b")
STOP_WORDS = {
    "para",
    "como",
    "este",
    "esta",
    "estos",
    "estas",
    "desde",
    "hasta",
    "sobre",
    "entre",
    "tiene",
    "puede",
    "debe",
    "documento",
    "that",
    "this",
    "with",
    "from",
    "have",
    "will",
    "would",
    "could",
    "should",
    "about",
    "into",
    "your",
    "their",
}


class EvidenceVerificationRejected(ValueError):
    pass


class DocumentVerificationGateway(Protocol):
    name: str

    async def health(self) -> bool: ...

    async def verify(self, request: DocumentVerificationInput) -> ModelOutput: ...


def _terms(value: str) -> set[str]:
    return {word.casefold() for word in WORD.findall(value) if word.casefold() not in STOP_WORDS}


def _lexically_supported(statement: str, quotes: str) -> bool:
    statement_terms = _terms(statement)
    if not statement_terms:
        return False
    quote_terms = _terms(quotes)
    overlap = len(statement_terms & quote_terms) / len(statement_terms)
    statement_numbers = set(NUMBER.findall(statement))
    return overlap >= 0.15 and statement_numbers.issubset(set(NUMBER.findall(quotes)))


class DocumentEvidenceVerifier:
    """Verifica integridad, cita exacta, soporte y cobertura; después firma el resultado."""

    name = "independent-audit-verifier"

    def __init__(self, signer: Ed25519Signer) -> None:
        self.signer = signer

    async def health(self) -> bool:
        return True

    async def verify(self, request: DocumentVerificationInput) -> ModelOutput:
        context = request.context
        blocks = {block.id: block for block in context.blocks}
        sources = {source.document_id: source for source in context.source_versions}
        objections: list[str] = []
        for source_block in blocks.values():
            if (
                hashlib.sha256(source_block.text.encode("utf-8")).hexdigest()
                != source_block.text_hash
            ):
                raise EvidenceVerificationRejected(f"block integrity mismatch: {source_block.id}")
            source = sources.get(source_block.document_id)
            if source is None or source.version_id != source_block.version_id:
                raise EvidenceVerificationRejected(
                    f"block source binding mismatch: {source_block.id}"
                )

        evidence: dict[str, EvidenceReference] = {}
        invalid_evidence: set[str] = set()
        for citation in request.draft.citations:
            block = blocks.get(citation.block_id)
            source = sources.get(citation.document_id)
            valid = bool(
                block
                and source
                and citation.evidence_id not in evidence
                and block.document_id == citation.document_id
                and block.version_id == citation.version_id == source.version_id
                and citation.quote in block.text
            )
            if not valid:
                invalid_evidence.add(citation.evidence_id)
                continue
            evidence[citation.evidence_id] = citation
        if invalid_evidence:
            objections.append(
                "Se descartaron citas sin coincidencia literal o sin unión válida a la versión: "
                + ", ".join(sorted(invalid_evidence))
            )

        accepted_claims: list[DocumentClaim] = []
        rejected_claims: list[str] = []
        for claim in request.draft.claims:
            references = [evidence.get(item) for item in claim.evidence_ids]
            if not references or any(item is None for item in references):
                rejected_claims.append(claim.id)
                continue
            supporting_text = "\n".join(item.quote for item in references if item is not None)
            if not _lexically_supported(claim.statement, supporting_text):
                rejected_claims.append(claim.id)
                continue
            accepted_claims.append(claim)
        if rejected_claims:
            objections.append(
                "Afirmaciones descartadas por soporte léxico insuficiente o evidencia inválida: "
                + ", ".join(rejected_claims)
            )
        if not accepted_claims:
            raise EvidenceVerificationRejected("no claim survived independent evidence checks")

        # Los avisos y límites detectados durante la ingesta se incorporan aunque el LLM los omita.
        limitations: list[DocumentLimitation] = []
        valid_ids = set(evidence)
        for limitation in request.draft.limitations:
            if all(item in valid_ids for item in limitation.evidence_ids):
                limitations.append(limitation)
        critical_evidence: list[tuple[DocumentBlock, EvidenceReference]] = []
        for block_id in context.critical_block_ids:
            critical_block = blocks.get(block_id)
            if critical_block is None:
                objections.append(
                    f"El bloque crítico {block_id} quedó fuera del contexto analizado."
                )
                continue
            existing = next((item for item in evidence.values() if item.block_id == block_id), None)
            if existing is None:
                source = sources[critical_block.document_id]
                evidence_id = f"E-SYS-{len(evidence) + 1}"
                existing = EvidenceReference(
                    evidence_id=evidence_id,
                    document_id=critical_block.document_id,
                    version_id=critical_block.version_id,
                    block_id=critical_block.id,
                    label=source.label,
                    quote=critical_block.text[:10_000],
                    page_number=critical_block.page_number,
                    section_path=critical_block.section_path,
                    relation="limits",
                )
                evidence[evidence_id] = existing
                valid_ids.add(evidence_id)
            critical_evidence.append((critical_block, existing))

        # Todos los bloques críticos se sellan por separado, pero se presentan agrupados por
        # secciones contiguas. La exhaustividad de Audit no debe convertir la respuesta humana
        # en una repetición de cada encabezado, línea de código y elemento de lista.
        for run in _critical_runs(critical_evidence):
            for offset in range(0, len(run), 20):
                chunk = run[offset : offset + 20]
                evidence_ids = [item[1].evidence_id for item in chunk]
                if all(
                    any(evidence_id in item.evidence_ids for item in limitations)
                    for evidence_id in evidence_ids
                ):
                    continue
                title = _shared_section_title([item[0].section_path for item in chunk])
                limitations.append(
                    DocumentLimitation(
                        id=new_id("limitation"),
                        statement=(
                            f"Sheily preservó {len(chunk)} bloques de la sección crítica "
                            f"«{title}» para impedir que sus requisitos, avisos o límites "
                            "desaparezcan del informe."
                        ),
                        evidence_ids=evidence_ids,
                        system_detected=True,
                    )
                )

        contradictions: list[DocumentContradiction] = []
        for item in request.draft.contradictions:
            if len(set(item.evidence_ids)) >= 2 and all(
                evidence_id in valid_ids for evidence_id in item.evidence_ids
            ):
                contradictions.append(item)
        unknowns = list(dict.fromkeys(request.draft.unknowns))
        for artifact in context.missing_artifacts:
            unknowns.append(
                f"El documento menciona {artifact}, pero ese artefacto no fue adjuntado; "
                "su contenido y funcionamiento no se han comprobado."
            )
        unknowns = list(dict.fromkeys(unknowns))

        cited_blocks = {item.block_id for item in evidence.values()}
        critical = set(context.critical_block_ids)
        coverage = CoverageReport(
            total_blocks=len(context.total_block_ids),
            analyzed_blocks=len(context.analyzed_block_ids),
            cited_blocks=len(cited_blocks),
            critical_blocks=len(critical),
            cited_critical_blocks=len(cited_blocks & critical),
            ratio=round(len(context.analyzed_block_ids) / len(context.total_block_ids), 6),
            omitted_block_ids=[
                item for item in context.total_block_ids if item not in context.analyzed_block_ids
            ],
        )
        if coverage.omitted_block_ids:
            objections.append(
                "El presupuesto de contexto dejó "
                f"{len(coverage.omitted_block_ids)} bloques fuera del análisis."
            )
        objections.append(
            "La coincidencia literal y el soporte léxico fueron comprobados; la implicación "
            "semántica completa no constituye una prueba formal."
        )
        bundle = EvidenceBundle(
            mission_id=request.mission_id,
            source_versions=[item.model_dump(mode="json") for item in context.source_versions],
            evidence=list(evidence.values()),
            claims=accepted_claims,
            transformations=[
                "extracción estructural versionada",
                context.selection_method,
                "redacción local por LLM",
                "verificación independiente de hash, unión, cita exacta, "
                "soporte léxico y cobertura",
            ],
            assumptions=request.draft.assumptions,
            counterevidence=contradictions,
            open_objections=objections,
            invalidation_conditions=[
                "el hash de una fuente o bloque deja de coincidir",
                "una cita exacta no aparece en la versión declarada",
                "nueva evidencia contradice una afirmación aceptada",
            ],
            coverage=coverage,
        )
        bundle_hash = canonical_hash(bundle.model_dump(mode="json"))
        signed_at = utc_now()
        report_body = {
            "status": "passed-with-open-objections",
            "verification_method": "structural-exact-quote-and-lexical-v1",
            "evidence_bundle_hash": bundle_hash,
            "verified_claim_ids": [item.id for item in accepted_claims],
            "rejected_claim_ids": rejected_claims,
            "open_objections": objections,
            "signed_at": signed_at.isoformat().replace("+00:00", "Z"),
            "key_id": self.signer.key_id,
            "algorithm": "Ed25519",
        }
        report_hash = canonical_hash(report_body)
        signed_payload = {**report_body, "report_hash": report_hash}
        report = DocumentVerificationReport.model_validate(
            {
                **signed_payload,
                "signature": self.signer.sign(DOCUMENT_VERIFICATION_DOMAIN, signed_payload),
            }
        )
        answer = _render_verified_answer(
            accepted_claims,
            evidence,
            contradictions,
            limitations,
            unknowns,
            coverage,
        )
        return ModelOutput(
            answer=answer,
            citations=list(evidence.values()),
            claims=accepted_claims,
            contradictions=contradictions,
            limitations=limitations,
            unknowns=unknowns,
            assumptions=request.draft.assumptions,
            coverage=coverage,
            evidence_bundle=bundle,
            verification_report=report,
        )


def _render_verified_answer(
    claims: list[DocumentClaim],
    evidence: dict[str, EvidenceReference],
    contradictions: list[DocumentContradiction],
    limitations: list[DocumentLimitation],
    unknowns: list[str],
    coverage: CoverageReport,
) -> str:
    lines = ["## Síntesis respaldada por evidencia"]
    for claim in claims:
        refs = ", ".join(f"[{item}]" for item in claim.evidence_ids)
        status = claim.epistemic_status.replace("-", " ")
        lines.append(f"- {claim.statement} {refs} — {status}; confianza {claim.confidence:.0%}.")
    if contradictions:
        lines.extend(["", "## Contradicciones o desacuerdos preservados"])
        lines.extend(
            f"- {item.statement} ({', '.join(item.evidence_ids)})" for item in contradictions
        )
    if limitations:
        lines.extend(["", "## Límites y advertencias"])
        lines.extend(
            f"- {item.statement}"
            + (f" ({', '.join(item.evidence_ids)})" if item.evidence_ids else "")
            for item in limitations
        )
    if unknowns:
        lines.extend(["", "## No comprobado"])
        lines.extend(f"- {item}" for item in unknowns)
    lines.extend(
        [
            "",
            "## Cobertura",
            f"Se analizaron {coverage.analyzed_blocks} de {coverage.total_blocks} bloques "
            f"({coverage.ratio:.1%}); {coverage.cited_blocks} bloques respaldan el resultado.",
            "",
            "## Evidencia literal de las afirmaciones aceptadas",
        ]
    )
    displayed_ids = list(
        dict.fromkeys(evidence_id for claim in claims for evidence_id in claim.evidence_ids)
    )
    for evidence_id in displayed_ids:
        item = evidence[evidence_id]
        location = " › ".join(item.section_path) or "sin sección"
        if item.page_number:
            location += f", página {item.page_number}"
        lines.append(f"- [{evidence_id}] {item.label} — {location}: «{item.quote}»")
    sealed_only = len(evidence) - len(displayed_ids)
    if sealed_only:
        lines.append(
            f"- Otros {sealed_only} fragmentos críticos quedaron sellados en el paquete de "
            "evidencia y están disponibles en los detalles del informe."
        )
    return "\n".join(lines)


def _critical_runs(
    items: list[tuple[DocumentBlock, EvidenceReference]],
) -> list[list[tuple[DocumentBlock, EvidenceReference]]]:
    """Agrupa bloques críticos adyacentes sin perder ninguna referencia sellada."""

    runs: list[list[tuple[DocumentBlock, EvidenceReference]]] = []
    for item in items:
        block = item[0]
        if not runs:
            runs.append([item])
            continue
        previous = runs[-1][-1][0]
        if block.document_id == previous.document_id and block.ordinal == previous.ordinal + 1:
            runs[-1].append(item)
        else:
            runs.append([item])
    return runs


def _shared_section_title(paths: list[list[str]]) -> str:
    if not paths:
        return "contenido crítico sin sección"
    prefix = list(paths[0])
    for path in paths[1:]:
        while prefix and path[: len(prefix)] != prefix:
            prefix.pop()
    return prefix[-1] if prefix else "contenido crítico sin sección"


class RemoteDocumentVerificationClient:
    name = "remote-independent-audit-verifier"

    def __init__(self, base_url: str, *, service_token: str, timeout_seconds: float = 20.0) -> None:
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

    async def verify(self, request: DocumentVerificationInput) -> ModelOutput:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/v1/document-verifications",
                    json=request.model_dump(mode="json"),
                    headers={"X-Noosfera-Service-Token": self.service_token},
                )
        except httpx.HTTPError as exc:
            raise EvidenceVerificationRejected("independent audit verifier is unavailable") from exc
        if response.status_code != 200:
            raise EvidenceVerificationRejected(
                f"independent audit verifier rejected the draft: {response.text[:500]}"
            )
        return ModelOutput.model_validate(response.json())
