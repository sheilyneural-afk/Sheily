"""Ingesta limitada de documentos de texto y PDF."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader

from noosfera_core.agent.models import DocumentRecord, new_id, utc_now

ALLOWED_MEDIA_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/pdf",
}


class DocumentRejected(ValueError):
    pass


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
    try:
        if media_type == "application/pdf":
            reader = PdfReader(io.BytesIO(content), strict=True)
            if len(reader.pages) > 200:
                raise DocumentRejected("PDF exceeds page limit")
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        else:
            text = content.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, DocumentRejected):
            raise
        raise DocumentRejected("document cannot be decoded safely") from exc
    normalized = text.strip()
    if not normalized:
        raise DocumentRejected("document contains no extractable text")
    return DocumentRecord(
        id=new_id("document"),
        user_id=user_id,
        name=safe_name,
        media_type=media_type,
        content_hash=hashlib.sha256(content).hexdigest(),
        text=normalized,
        size_bytes=len(content),
        created_at=utc_now(),
    )
