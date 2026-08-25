"""Ingesta estructural: conserva versión, páginas, secciones, bloques y hashes."""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader

from noosfera_core.agent.models import DocumentBlock, DocumentRecord, new_id, utc_now

ALLOWED_MEDIA_TYPES = {"text/plain", "text/markdown", "text/csv", "application/pdf"}
CRITICAL_TERMS = re.compile(
    r"\b(?:advertencias?|avisos?|importante|limitaciones?|restricciones?|riesgos?|"
    r"seguridad|incompatib|requisitos?|prerrequisitos?|dependencias?|requiere|necesitas?|"
    r"no incluye|soluci[oó]n de problemas|"
    r"warning|caveat|limitation|restriction|risk|required|prerequisite)\b",
    re.IGNORECASE,
)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+] |\d+[.)]\s+)")


class DocumentRejected(ValueError):
    pass


def _sha256(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def _bounded_chunks(value: str, maximum: int = 3_500) -> list[str]:
    chunks: list[str] = []
    pending = value.strip()
    while len(pending) > maximum:
        cut = max(pending.rfind("\n", 0, maximum), pending.rfind(" ", 0, maximum))
        if cut < maximum // 2:
            cut = maximum
        chunks.append(pending[:cut].strip())
        pending = pending[cut:].strip()
    if pending:
        chunks.append(pending)
    return chunks


def _split_markdown(text: str) -> list[tuple[str, str, list[str]]]:
    """Devuelve (tipo, texto, ruta de sección) sin borrar estructura del original."""

    result: list[tuple[str, str, list[str]]] = []
    sections: list[str] = []
    buffer: list[str] = []
    buffer_kind = "paragraph"
    in_code = False

    def flush() -> None:
        nonlocal buffer
        value = "\n".join(buffer).strip()
        if value:
            result.extend((buffer_kind, chunk, list(sections)) for chunk in _bounded_chunks(value))
        buffer = []

    for line in text.splitlines():
        heading = HEADING.match(line) if not in_code else None
        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            sections[:] = sections[: level - 1]
            sections.append(title)
            result.append(("heading", line.strip(), list(sections)))
            continue
        if line.strip().startswith("```"):
            if not in_code:
                flush()
                buffer_kind = "code"
                in_code = True
            buffer.append(line)
            if len(buffer) > 1 and line.strip() == "```":
                flush()
                buffer_kind = "paragraph"
                in_code = False
            continue
        if in_code:
            buffer.append(line)
            continue
        if not line.strip():
            flush()
            buffer_kind = "paragraph"
            continue
        kind = "list" if LIST_ITEM.match(line) else "table" if "|" in line else "paragraph"
        if buffer and kind != buffer_kind:
            flush()
        buffer_kind = kind
        buffer.append(line)
    flush()
    return result


def _split_plain(text: str, *, table: bool = False) -> list[tuple[str, str, list[str]]]:
    kind = "table" if table else "paragraph"
    chunks = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    if not chunks:
        chunks = [line.strip() for line in text.splitlines() if line.strip()]
    return [
        (kind, bounded, [])
        for chunk in chunks
        for bounded in _bounded_chunks(chunk)
    ]


def build_blocks(
    *, document_id: str, version_id: str, pages: list[str], media_type: str
) -> tuple[str, list[DocumentBlock]]:
    normalized_pages = [page.strip().replace("\r\n", "\n") for page in pages]
    normalized = "\n\n".join(page for page in normalized_pages if page).strip()
    blocks: list[DocumentBlock] = []
    global_cursor = 0
    ordinal = 0
    for page_index, page in enumerate(normalized_pages, start=1):
        if not page:
            continue
        parts = (
            _split_markdown(page)
            if media_type == "text/markdown"
            else _split_plain(page, table=media_type == "text/csv")
        )
        local_cursor = 0
        page_start = normalized.find(page, global_cursor)
        if page_start < 0:
            page_start = global_cursor
        for kind, value, section_path in parts:
            ordinal += 1
            local_start = page.find(value, local_cursor)
            if local_start < 0:
                local_start = local_cursor
            start = page_start + local_start
            end = start + len(value)
            local_cursor = local_start + len(value)
            text_hash = _sha256(value)
            block_id = (
                f"urn:noosfera:document-block:{version_id.rsplit(':', 1)[-1]}:"
                f"{ordinal:05d}:{text_hash[:16]}"
            )
            critical_text = " ".join([*section_path, value[:500]])
            blocks.append(
                DocumentBlock(
                    id=block_id,
                    document_id=document_id,
                    version_id=version_id,
                    ordinal=ordinal,
                    kind=kind,  # type: ignore[arg-type]
                    page_number=page_index if len(normalized_pages) > 1 else None,
                    section_path=section_path,
                    char_start=start,
                    char_end=end,
                    text_hash=text_hash,
                    text=value,
                    extraction_confidence=0.9 if media_type == "application/pdf" else 1.0,
                    critical=bool(CRITICAL_TERMS.search(critical_text)),
                )
            )
        global_cursor = page_start + len(page)
    if not blocks:
        raise DocumentRejected("document contains no extractable blocks")
    return normalized, blocks


async def parse_upload(upload: UploadFile, *, user_id: str, max_bytes: int) -> DocumentRecord:
    content = await upload.read(max_bytes + 1)
    await upload.close()
    if not content:
        raise DocumentRejected("document is empty")
    if len(content) > max_bytes:
        raise DocumentRejected("document exceeds configured size limit")
    media_type = (upload.content_type or "application/octet-stream").split(";", 1)[0]
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise DocumentRejected("unsupported document type")
    safe_name = Path(upload.filename or "document").name[:200]
    content_hash = _sha256(content)
    document_id = new_id("document")
    version_id = f"urn:noosfera:document-version:{content_hash}"
    try:
        if media_type == "application/pdf":
            reader = PdfReader(io.BytesIO(content), strict=True)
            if len(reader.pages) > 200:
                raise DocumentRejected("PDF exceeds page limit")
            pages = [(page.extract_text() or "") for page in reader.pages]
        else:
            pages = [content.decode("utf-8")]
    except (UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, DocumentRejected):
            raise
        raise DocumentRejected("document cannot be decoded safely") from exc
    normalized, blocks = build_blocks(
        document_id=document_id,
        version_id=version_id,
        pages=pages,
        media_type=media_type,
    )
    if not normalized:
        raise DocumentRejected("document contains no extractable text")
    return DocumentRecord(
        id=document_id,
        user_id=user_id,
        name=safe_name,
        media_type=media_type,
        content_hash=content_hash,
        normalized_hash=_sha256(normalized),
        version_id=version_id,
        text=normalized,
        blocks=blocks,
        size_bytes=len(content),
        created_at=utc_now(),
    )
