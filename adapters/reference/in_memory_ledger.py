from __future__ import annotations

from typing import Any

from noosfera_core.audit import create_receipt


class InMemoryLedger:
    def __init__(self) -> None:
        self.receipts: list[dict[str, Any]] = []

    async def append(self, event: dict[str, Any]) -> dict[str, Any]:
        previous = self.receipts[-1]["receipt_hash"] if self.receipts else "0" * 64
        receipt = create_receipt(event, previous)
        value = {
            "event_hash": receipt.event_hash,
            "previous_receipt_hash": receipt.previous_receipt_hash,
            "receipt_hash": receipt.receipt_hash,
        }
        self.receipts.append(value)
        return value
