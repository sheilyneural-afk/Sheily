"""Recibos de auditoría encadenados sin incluir el contenido observado."""

from __future__ import annotations

from dataclasses import dataclass

from noosfera_core.hashing import canonical_hash


@dataclass(frozen=True)
class AuditReceipt:
    event_hash: str
    previous_receipt_hash: str
    receipt_hash: str


def create_receipt(event: dict[str, object], previous_receipt_hash: str) -> AuditReceipt:
    event_hash = canonical_hash(event)
    receipt_hash = canonical_hash(
        {"event_hash": event_hash, "previous_receipt_hash": previous_receipt_hash}
    )
    return AuditReceipt(event_hash, previous_receipt_hash, receipt_hash)
