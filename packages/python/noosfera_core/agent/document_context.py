"""Selección reproducible de evidencia: críticos primero y relevancia léxica después."""

from __future__ import annotations

import math
import re
from collections import Counter

from noosfera_core.agent.models import (
    DocumentBlock,
    DocumentEvidenceContext,
    DocumentRecord,
    DocumentSourceVersion,
)

TOKEN = re.compile(r"[\wáéíóúüñ]{2,}", re.IGNORECASE)
ARTIFACT = re.compile(
    r"(?<![\w./-])([\w.-]+\.(?:py|rs|js|ts|json|ya?ml|toml|sh|jar|zip|mcworld|schem))(?![\w.-])",
    re.IGNORECASE,
)


def _tokens(value: str) -> list[str]:
    return [item.casefold() for item in TOKEN.findall(value)]


def _score(query: Counter[str], text: str, document_frequency: Counter[str], total: int) -> float:
    terms = Counter(_tokens(text))
    length = max(sum(terms.values()), 1)
    score = 0.0
    for term, query_count in query.items():
        frequency = terms.get(term, 0)
        if not frequency:
            continue
        inverse = math.log(1 + (total + 1) / (document_frequency.get(term, 0) + 1))
        score += query_count * inverse * frequency / (frequency + 0.5 + 1.5 * length / 200)
    return score


def build_document_context(
    prompt: str,
    documents: list[DocumentRecord],
    *,
    max_chars: int,
    max_blocks: int = 32,
) -> DocumentEvidenceContext:
    if not documents:
        raise ValueError("document context requires at least one authorized document")
    all_blocks = [block for document in documents for block in document.blocks]
    if not all_blocks:
        raise ValueError("authorized documents contain no addressable blocks")
    query = Counter(_tokens(prompt))
    document_frequency: Counter[str] = Counter()
    for block in all_blocks:
        document_frequency.update(set(_tokens(" ".join([*block.section_path, block.text]))))
    scores = {
        block.id: _score(
            query,
            " ".join([*block.section_path, block.text]),
            document_frequency,
            len(all_blocks),
        )
        for block in all_blocks
    }
    selected: dict[str, DocumentBlock] = {}
    used = 0

    def include(block: DocumentBlock) -> None:
        nonlocal used
        block_id = block.id
        if block_id in selected:
            return
        selected[block_id] = block
        used += len(block.text)

    # Every source is represented, then warnings/limits can never be optimized away.
    for document in documents:
        include(document.blocks[0])
    for block in all_blocks:
        if block.critical:
            include(block)
    for block in sorted(
        all_blocks,
        key=lambda item: (scores[item.id], item.kind == "heading", -item.ordinal),
        reverse=True,
    ):
        if block.id in selected:
            continue
        if len(selected) >= max_blocks:
            continue
        if used + len(block.text) > max_chars and selected:
            continue
        include(block)
    chosen = sorted(selected.values(), key=lambda item: (item.document_id, item.ordinal))
    uploaded_names = {document.name.casefold() for document in documents}
    referenced = {
        match.group(1)
        for block in all_blocks
        for match in ARTIFACT.finditer(block.text)
    }
    missing = sorted(name for name in referenced if name.casefold() not in uploaded_names)
    return DocumentEvidenceContext(
        source_versions=[
            DocumentSourceVersion(
                document_id=document.id,
                version_id=document.version_id,
                label=document.name,
                media_type=document.media_type,
                content_hash=document.content_hash,
                normalized_hash=document.normalized_hash,
                extractor=document.extractor,
                extractor_version=document.extractor_version,
                total_blocks=len(document.blocks),
            )
            for document in documents
        ],
        blocks=chosen,
        total_block_ids=[block.id for block in all_blocks],
        analyzed_block_ids=[block.id for block in chosen],
        critical_block_ids=[block.id for block in all_blocks if block.critical],
        missing_artifacts=missing,
    )
