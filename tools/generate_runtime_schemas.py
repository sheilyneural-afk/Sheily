#!/usr/bin/env python3
"""Genera contratos JSON Schema de las fronteras ejecutables 0.3."""

from __future__ import annotations

import json
from pathlib import Path

from noosfera_core.agent.models import (
    ApprovalReceipt,
    AuditAnchor,
    CapabilityGrant,
    CognitiveCycle,
    PlanAttestation,
    RevocationDirective,
    StopDirective,
)
from noosfera_core.agent.self_model import SelfModelSnapshot

ROOT = Path(__file__).resolve().parents[1]

MODELS = {
    "approval-receipt.schema.json": ApprovalReceipt,
    "audit-anchor.schema.json": AuditAnchor,
    "capability-grant.schema.json": CapabilityGrant,
    "cognitive-cycle.schema.json": CognitiveCycle,
    "plan-attestation.schema.json": PlanAttestation,
    "revocation-directive.schema.json": RevocationDirective,
    "self-model.schema.json": SelfModelSnapshot,
    "stop-directive.schema.json": StopDirective,
}


def main() -> None:
    for filename, model in MODELS.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://noosfera.invalid/schemas/{filename}"
        target = ROOT / "schemas" / filename
        target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
