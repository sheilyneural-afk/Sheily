"""Anclaje firmado de la auditoría append-only."""

from __future__ import annotations

import json
from typing import Any

from noosfera_core.agent.crypto import Ed25519Signer
from noosfera_core.agent.models import AuditAnchor, ModelOutput, new_id, utc_now
from noosfera_core.hashing import canonical_hash

AUDIT_ANCHOR_DOMAIN = "noosfera.audit.anchor.v1"
ZERO_HASH = "0" * 64


class AuditIntegrityError(RuntimeError):
    pass


def merkle_root(receipts: list[str]) -> str:
    if not receipts:
        raise AuditIntegrityError("cannot anchor an empty audit log")
    level = list(receipts)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            canonical_hash([level[index], level[index + 1]]) for index in range(0, len(level), 2)
        ]
    return level[0]


class AuditAnchorStore:
    def __init__(self, database_url: str, signer: Ed25519Signer) -> None:
        self.database_url = database_url
        self.signer = signer
        self._pool: Any = None

    async def initialize(self) -> None:
        import asyncpg  # type: ignore[import-untyped]

        self._pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        await self._pool.execute(
            """CREATE TABLE IF NOT EXISTS audit_document_verifications (
                 report_hash CHAR(64) PRIMARY KEY,
                 evidence_bundle_hash CHAR(64) NOT NULL,
                 key_id TEXT NOT NULL,
                 payload JSONB NOT NULL,
                 created_at TIMESTAMPTZ NOT NULL
               )"""
        )
        await self._pool.execute(
            """DO $$
               BEGIN
                 IF NOT EXISTS (
                   SELECT 1 FROM pg_trigger
                   WHERE tgname='audit_document_verifications_append_only'
                 ) THEN
                   CREATE TRIGGER audit_document_verifications_append_only
                     BEFORE UPDATE OR DELETE ON audit_document_verifications
                     FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();
                 END IF;
               END
               $$;"""
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def health(self) -> bool:
        try:
            return bool(self._pool and await self._pool.fetchval("SELECT 1"))
        except Exception:  # noqa: BLE001
            return False

    def _require_pool(self) -> Any:
        if self._pool is None:
            raise RuntimeError("audit store is not initialized")
        return self._pool

    async def create_anchor(self) -> AuditAnchor:
        rows = await self._require_pool().fetch(
            """SELECT mission_id,sequence,event_hash,previous_receipt_hash,
                      receipt_hash,created_at
               FROM agent_events
               UNION ALL
               SELECT $1 AS mission_id,sequence,event_hash,previous_receipt_hash,
                      receipt_hash,created_at
               FROM agent_control_events
               ORDER BY created_at,mission_id,sequence""",
            "urn:noosfera:mission:operator-control",
        )
        if not rows:
            raise AuditIntegrityError("cannot anchor an empty audit log")
        previous_by_mission: dict[str, str] = {}
        receipts: list[str] = []
        event_ids: list[str] = []
        for row in rows:
            mission_id = str(row["mission_id"])
            previous = previous_by_mission.get(mission_id, ZERO_HASH)
            if str(row["previous_receipt_hash"]) != previous:
                raise AuditIntegrityError(f"broken receipt chain for {mission_id}")
            expected = canonical_hash(
                {
                    "event_hash": str(row["event_hash"]),
                    "previous_receipt_hash": previous,
                }
            )
            if expected != str(row["receipt_hash"]):
                raise AuditIntegrityError(f"invalid receipt hash for {mission_id}")
            receipt = str(row["receipt_hash"])
            previous_by_mission[mission_id] = receipt
            receipts.append(receipt)
            event_ids.append(f"{mission_id}#{int(row['sequence'])}")
        pending = AuditAnchor(
            id=new_id("audit-anchor"),
            first_event=event_ids[0],
            last_event=event_ids[-1],
            event_count=len(event_ids),
            merkle_root=merkle_root(receipts),
            created_at=utc_now(),
            key_id=self.signer.key_id,
            signature="pending",
        )
        payload = pending.model_dump(mode="json", exclude={"signature"})
        anchor = pending.model_copy(
            update={"signature": self.signer.sign(AUDIT_ANCHOR_DOMAIN, payload)}
        )
        await self._require_pool().execute(
            """INSERT INTO audit_anchors
                 (id,first_event,last_event,event_count,merkle_root,payload,created_at)
               VALUES($1,$2,$3,$4,$5,$6::jsonb,$7)""",
            anchor.id,
            anchor.first_event,
            anchor.last_event,
            anchor.event_count,
            anchor.merkle_root,
            anchor.model_dump_json(),
            anchor.created_at,
        )
        return anchor

    async def list_anchors(self, limit: int = 100) -> list[AuditAnchor]:
        rows = await self._require_pool().fetch(
            "SELECT payload FROM audit_anchors ORDER BY created_at DESC LIMIT $1", limit
        )
        return [
            AuditAnchor.model_validate(
                json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
            )
            for row in rows
        ]

    async def save_document_verification(self, output: ModelOutput) -> None:
        if output.verification_report is None or output.evidence_bundle is None:
            raise ValueError("document verification output has no proof")
        await self._require_pool().execute(
            """INSERT INTO audit_document_verifications
                 (report_hash,evidence_bundle_hash,key_id,payload,created_at)
               VALUES($1,$2,$3,$4::jsonb,$5)""",
            output.verification_report.report_hash,
            output.verification_report.evidence_bundle_hash,
            output.verification_report.key_id,
            output.model_dump_json(),
            output.verification_report.signed_at,
        )
