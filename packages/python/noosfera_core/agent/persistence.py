"""Persistencia funcional para conversaciones, misiones, memoria y auditoría."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, Protocol

from noosfera_core.agent.models import (
    AuditEntry,
    Conversation,
    DocumentRecord,
    MemoryRecord,
    Message,
    Mission,
    MissionEvent,
    new_id,
    utc_now,
)
from noosfera_core.audit import create_receipt

CONTROL_MISSION_ID = "urn:noosfera:mission:operator-control"


class StateStore(Protocol):
    backend_name: str

    async def initialize(self) -> None: ...

    async def close(self) -> None: ...

    async def health(self) -> bool: ...

    async def create_conversation(self, conversation: Conversation) -> None: ...

    async def get_conversation(self, conversation_id: str, user_id: str) -> Conversation | None: ...

    async def add_message(self, message: Message) -> None: ...

    async def list_messages(self, conversation_id: str, user_id: str) -> list[Message]: ...

    async def save_document(self, document: DocumentRecord) -> None: ...

    async def get_documents(
        self, document_ids: list[str], user_id: str
    ) -> list[DocumentRecord]: ...

    async def create_mission(self, mission: Mission) -> None: ...

    async def save_mission(self, mission: Mission) -> None: ...

    async def get_mission(self, mission_id: str, user_id: str) -> Mission | None: ...

    async def append_event(
        self, mission_id: str, event_type: str, payload: dict[str, Any]
    ) -> MissionEvent: ...

    async def list_events(self, mission_id: str, after: int = 0) -> list[MissionEvent]: ...

    async def save_memory(self, memory: MemoryRecord) -> None: ...

    async def list_memories(self, user_id: str) -> list[MemoryRecord]: ...

    async def delete_memory(self, memory_id: str, user_id: str) -> bool: ...

    async def list_audit(self, limit: int = 200) -> list[AuditEntry]: ...

    async def append_control_event(
        self, event_type: str, payload: dict[str, Any]
    ) -> MissionEvent: ...

    async def set_stop(self, active: bool, reason: str) -> None: ...

    async def get_stop(self) -> tuple[bool, str]: ...


class InMemoryStateStore:
    backend_name = "memory"

    def __init__(self) -> None:
        self.conversations: dict[str, Conversation] = {}
        self.messages: dict[str, list[Message]] = defaultdict(list)
        self.documents: dict[str, DocumentRecord] = {}
        self.missions: dict[str, Mission] = {}
        self.events: dict[str, list[MissionEvent]] = defaultdict(list)
        self.memories: dict[str, MemoryRecord] = {}
        self.stop_active = False
        self.stop_reason = ""
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def health(self) -> bool:
        return True

    async def create_conversation(self, conversation: Conversation) -> None:
        self.conversations[conversation.id] = conversation

    async def get_conversation(self, conversation_id: str, user_id: str) -> Conversation | None:
        value = self.conversations.get(conversation_id)
        return value if value and value.user_id == user_id else None

    async def add_message(self, message: Message) -> None:
        self.messages[message.conversation_id].append(message)

    async def list_messages(self, conversation_id: str, user_id: str) -> list[Message]:
        conversation = await self.get_conversation(conversation_id, user_id)
        return list(self.messages[conversation_id]) if conversation else []

    async def save_document(self, document: DocumentRecord) -> None:
        self.documents[document.id] = document

    async def get_documents(self, document_ids: list[str], user_id: str) -> list[DocumentRecord]:
        return [
            document
            for document_id in document_ids
            if (document := self.documents.get(document_id)) and document.user_id == user_id
        ]

    async def create_mission(self, mission: Mission) -> None:
        self.missions[mission.id] = mission

    async def save_mission(self, mission: Mission) -> None:
        self.missions[mission.id] = mission

    async def get_mission(self, mission_id: str, user_id: str) -> Mission | None:
        value = self.missions.get(mission_id)
        return value if value and value.user_id == user_id else None

    async def append_event(
        self, mission_id: str, event_type: str, payload: dict[str, Any]
    ) -> MissionEvent:
        async with self._lock:
            sequence = len(self.events[mission_id]) + 1
            previous = self.events[mission_id][-1].receipt_hash if sequence > 1 else "0" * 64
            created_at = utc_now()
            event_body = {
                "mission_id": mission_id,
                "sequence": sequence,
                "event_type": event_type,
                "payload": payload,
                "created_at": created_at.isoformat(),
            }
            receipt = create_receipt(event_body, previous)
            event = MissionEvent(
                mission_id=mission_id,
                sequence=sequence,
                event_type=event_type,
                payload=payload,
                created_at=created_at,
                event_hash=receipt.event_hash,
                previous_receipt_hash=receipt.previous_receipt_hash,
                receipt_hash=receipt.receipt_hash,
            )
            self.events[mission_id].append(event)
            return event

    async def list_events(self, mission_id: str, after: int = 0) -> list[MissionEvent]:
        return [event for event in self.events[mission_id] if event.sequence > after]

    async def save_memory(self, memory: MemoryRecord) -> None:
        self.memories[memory.id] = memory

    async def list_memories(self, user_id: str) -> list[MemoryRecord]:
        return [
            memory
            for memory in self.memories.values()
            if memory.user_id == user_id and memory.deleted_at is None
        ]

    async def delete_memory(self, memory_id: str, user_id: str) -> bool:
        memory = self.memories.get(memory_id)
        if not memory or memory.user_id != user_id or memory.deleted_at is not None:
            return False
        self.memories[memory_id] = memory.model_copy(update={"deleted_at": utc_now()})
        return True

    async def list_audit(self, limit: int = 200) -> list[AuditEntry]:
        entries = [
            AuditEntry(
                mission_id=event.mission_id,
                sequence=event.sequence,
                event_type=event.event_type,
                event_hash=event.event_hash,
                previous_receipt_hash=event.previous_receipt_hash,
                receipt_hash=event.receipt_hash,
                created_at=event.created_at,
            )
            for events in self.events.values()
            for event in events
        ]
        return sorted(entries, key=lambda item: item.created_at, reverse=True)[:limit]

    async def append_control_event(self, event_type: str, payload: dict[str, Any]) -> MissionEvent:
        return await self.append_event(CONTROL_MISSION_ID, event_type, payload)

    async def set_stop(self, active: bool, reason: str) -> None:
        self.stop_active = active
        self.stop_reason = reason

    async def get_stop(self) -> tuple[bool, str]:
        return self.stop_active, self.stop_reason


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_conversations (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_messages (
  id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES agent_conversations(id),
  role TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_documents (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, media_type TEXT NOT NULL,
  content_hash CHAR(64) NOT NULL, content_text TEXT NOT NULL, size_bytes BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
ALTER TABLE agent_documents ADD COLUMN IF NOT EXISTS normalized_hash CHAR(64);
ALTER TABLE agent_documents ADD COLUMN IF NOT EXISTS version_id TEXT;
ALTER TABLE agent_documents ADD COLUMN IF NOT EXISTS extractor TEXT;
ALTER TABLE agent_documents ADD COLUMN IF NOT EXISTS extractor_version TEXT;
CREATE TABLE IF NOT EXISTS agent_document_blocks (
  id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES agent_documents(id),
  version_id TEXT NOT NULL, ordinal INTEGER NOT NULL, kind TEXT NOT NULL,
  page_number INTEGER, section_path JSONB NOT NULL, char_start INTEGER NOT NULL,
  char_end INTEGER NOT NULL, text_hash CHAR(64) NOT NULL, content_text TEXT NOT NULL,
  extraction_confidence DOUBLE PRECISION NOT NULL, epistemic_status TEXT NOT NULL,
  critical BOOLEAN NOT NULL, UNIQUE(document_id, ordinal)
);
CREATE TABLE IF NOT EXISTS agent_missions (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
  status TEXT NOT NULL, payload JSONB NOT NULL, version BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_events (
  mission_id TEXT NOT NULL, sequence BIGINT NOT NULL, event_type TEXT NOT NULL,
  payload JSONB NOT NULL, event_hash CHAR(64) NOT NULL,
  previous_receipt_hash CHAR(64) NOT NULL, receipt_hash CHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL, PRIMARY KEY (mission_id, sequence)
);
CREATE TABLE IF NOT EXISTS agent_memories (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, purpose TEXT NOT NULL, content TEXT NOT NULL,
  source_mission_id TEXT NOT NULL, retention_days INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL, deleted_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS agent_control (
  key TEXT PRIMARY KEY, value JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_control_events (
  sequence BIGSERIAL PRIMARY KEY, event_type TEXT NOT NULL, payload JSONB NOT NULL,
  event_hash CHAR(64) NOT NULL, previous_receipt_hash CHAR(64) NOT NULL,
  receipt_hash CHAR(64) NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_messages_conversation
  ON agent_messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_missions_user ON agent_missions(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_documents_user ON agent_documents(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_document_blocks_document
  ON agent_document_blocks(document_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_agent_memories_user ON agent_memories(user_id, created_at DESC);
"""


def _decode_json(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        decoded = json.loads(value)
        if not isinstance(decoded, dict):
            raise ValueError("stored JSON value is not an object")
        return decoded
    return dict(value)


class PostgresStateStore:
    backend_name = "postgres"

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._pool: Any = None

    async def initialize(self) -> None:
        import asyncpg  # type: ignore[import-untyped]

        self._pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=10)
        async with self._pool.acquire() as connection:
            await connection.execute(SCHEMA_SQL)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def health(self) -> bool:
        if self._pool is None:
            return False
        try:
            return bool(await self._pool.fetchval("SELECT 1"))
        except Exception:  # noqa: BLE001 -- health must report false, not raise
            return False

    def _require_pool(self) -> Any:
        if self._pool is None:
            raise RuntimeError("postgres store is not initialized")
        return self._pool

    async def create_conversation(self, conversation: Conversation) -> None:
        await self._require_pool().execute(
            "INSERT INTO agent_conversations(id,user_id,title,created_at) VALUES($1,$2,$3,$4)",
            conversation.id,
            conversation.user_id,
            conversation.title,
            conversation.created_at,
        )

    async def get_conversation(self, conversation_id: str, user_id: str) -> Conversation | None:
        row = await self._require_pool().fetchrow(
            "SELECT * FROM agent_conversations WHERE id=$1 AND user_id=$2",
            conversation_id,
            user_id,
        )
        return Conversation.model_validate(dict(row)) if row else None

    async def add_message(self, message: Message) -> None:
        await self._require_pool().execute(
            """INSERT INTO agent_messages(id,conversation_id,role,content,created_at)
               VALUES($1,$2,$3,$4,$5)""",
            message.id,
            message.conversation_id,
            message.role,
            message.content,
            message.created_at,
        )

    async def list_messages(self, conversation_id: str, user_id: str) -> list[Message]:
        if not await self.get_conversation(conversation_id, user_id):
            return []
        rows = await self._require_pool().fetch(
            "SELECT * FROM agent_messages WHERE conversation_id=$1 ORDER BY created_at",
            conversation_id,
        )
        return [Message.model_validate(dict(row)) for row in rows]

    async def save_document(self, document: DocumentRecord) -> None:
        pool = self._require_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """INSERT INTO agent_documents
                   (id,user_id,name,media_type,content_hash,normalized_hash,version_id,
                    extractor,extractor_version,content_text,size_bytes,created_at)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                document.id,
                document.user_id,
                document.name,
                document.media_type,
                document.content_hash,
                document.normalized_hash,
                document.version_id,
                document.extractor,
                document.extractor_version,
                document.text,
                document.size_bytes,
                document.created_at,
            )
            await connection.executemany(
                """INSERT INTO agent_document_blocks
                   (id,document_id,version_id,ordinal,kind,page_number,section_path,
                    char_start,char_end,text_hash,content_text,extraction_confidence,
                    epistemic_status,critical)
                   VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12,$13,$14)""",
                [
                    (
                        block.id,
                        block.document_id,
                        block.version_id,
                        block.ordinal,
                        block.kind,
                        block.page_number,
                        json.dumps(block.section_path),
                        block.char_start,
                        block.char_end,
                        block.text_hash,
                        block.text,
                        block.extraction_confidence,
                        block.epistemic_status,
                        block.critical,
                    )
                    for block in document.blocks
                ],
            )

    async def get_documents(self, document_ids: list[str], user_id: str) -> list[DocumentRecord]:
        if not document_ids:
            return []
        pool = self._require_pool()
        rows = await pool.fetch(
            """SELECT id,user_id,name,media_type,content_hash,normalized_hash,version_id,
                      extractor,extractor_version,content_text AS text,size_bytes,created_at
               FROM agent_documents WHERE user_id=$1 AND id=ANY($2::text[]) ORDER BY created_at""",
            user_id,
            document_ids,
        )
        block_rows = await pool.fetch(
            """SELECT id,document_id,version_id,ordinal,kind,page_number,section_path,
                      char_start,char_end,text_hash,content_text AS text,extraction_confidence,
                      epistemic_status,critical
               FROM agent_document_blocks WHERE document_id=ANY($1::text[])
               ORDER BY document_id,ordinal""",
            document_ids,
        )
        from hashlib import sha256

        from noosfera_core.agent.documents import build_blocks
        from noosfera_core.agent.models import DocumentBlock

        blocks_by_document: dict[str, list[DocumentBlock]] = defaultdict(list)
        for row in block_rows:
            value = dict(row)
            value["section_path"] = (
                json.loads(value["section_path"])
                if isinstance(value["section_path"], str)
                else value["section_path"]
            )
            blocks_by_document[str(row["document_id"])].append(DocumentBlock.model_validate(value))
        documents: list[DocumentRecord] = []
        for row in rows:
            value = dict(row)
            document_id = str(value["id"])
            version_id = str(
                value.get("version_id")
                or f"urn:noosfera:document-version:{value['content_hash']}"
            )
            blocks = blocks_by_document.get(document_id, [])
            if not blocks:
                normalized, blocks = build_blocks(
                    document_id=document_id,
                    version_id=version_id,
                    pages=[str(value["text"])],
                    media_type=str(value["media_type"]),
                )
                value["text"] = normalized
            value.update(
                {
                    "version_id": version_id,
                    "normalized_hash": value.get("normalized_hash")
                    or sha256(str(value["text"]).encode()).hexdigest(),
                    "extractor": value.get("extractor") or "noosfera-structural-ingest",
                    "extractor_version": value.get("extractor_version") or "1.0.0",
                    "blocks": blocks,
                }
            )
            documents.append(DocumentRecord.model_validate(value))
        return documents

    async def create_mission(self, mission: Mission) -> None:
        await self._require_pool().execute(
            """INSERT INTO agent_missions
               (id,user_id,conversation_id,status,payload,version,created_at,updated_at)
               VALUES($1,$2,$3,$4,$5::jsonb,$6,$7,$8)""",
            mission.id,
            mission.user_id,
            mission.conversation_id,
            mission.status.value,
            mission.model_dump_json(),
            mission.version,
            mission.created_at,
            mission.updated_at,
        )

    async def save_mission(self, mission: Mission) -> None:
        result = await self._require_pool().execute(
            """UPDATE agent_missions SET status=$2,payload=$3::jsonb,version=$4,updated_at=$5
               WHERE id=$1""",
            mission.id,
            mission.status.value,
            mission.model_dump_json(),
            mission.version,
            mission.updated_at,
        )
        if result == "UPDATE 0":
            raise KeyError(mission.id)

    async def get_mission(self, mission_id: str, user_id: str) -> Mission | None:
        row = await self._require_pool().fetchrow(
            "SELECT payload FROM agent_missions WHERE id=$1 AND user_id=$2", mission_id, user_id
        )
        return Mission.model_validate(_decode_json(row["payload"])) if row else None

    async def append_event(
        self, mission_id: str, event_type: str, payload: dict[str, Any]
    ) -> MissionEvent:
        pool = self._require_pool()
        async with pool.acquire() as connection, connection.transaction():
            last = await connection.fetchrow(
                """SELECT sequence,receipt_hash FROM agent_events
                   WHERE mission_id=$1 ORDER BY sequence DESC LIMIT 1 FOR UPDATE""",
                mission_id,
            )
            sequence = int(last["sequence"]) + 1 if last else 1
            previous = str(last["receipt_hash"]) if last else "0" * 64
            created_at = utc_now()
            body = {
                "mission_id": mission_id,
                "sequence": sequence,
                "event_type": event_type,
                "payload": payload,
                "created_at": created_at.isoformat(),
            }
            receipt = create_receipt(body, previous)
            event = MissionEvent(
                mission_id=mission_id,
                sequence=sequence,
                event_type=event_type,
                payload=payload,
                created_at=created_at,
                event_hash=receipt.event_hash,
                previous_receipt_hash=receipt.previous_receipt_hash,
                receipt_hash=receipt.receipt_hash,
            )
            await connection.execute(
                """INSERT INTO agent_events
                   (mission_id,sequence,event_type,payload,event_hash,previous_receipt_hash,receipt_hash,created_at)
                   VALUES($1,$2,$3,$4::jsonb,$5,$6,$7,$8)""",
                mission_id,
                sequence,
                event_type,
                json.dumps(payload),
                event.event_hash,
                event.previous_receipt_hash,
                event.receipt_hash,
                created_at,
            )
            return event

    async def list_events(self, mission_id: str, after: int = 0) -> list[MissionEvent]:
        rows = await self._require_pool().fetch(
            """SELECT mission_id,sequence,event_type,payload,event_hash,previous_receipt_hash,
                      receipt_hash,created_at FROM agent_events
               WHERE mission_id=$1 AND sequence>$2 ORDER BY sequence""",
            mission_id,
            after,
        )
        return [
            MissionEvent.model_validate({**dict(row), "payload": _decode_json(row["payload"])})
            for row in rows
        ]

    async def save_memory(self, memory: MemoryRecord) -> None:
        await self._require_pool().execute(
            """INSERT INTO agent_memories
               (id,user_id,purpose,content,source_mission_id,retention_days,created_at,deleted_at)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
            memory.id,
            memory.user_id,
            memory.purpose,
            memory.content,
            memory.source_mission_id,
            memory.retention_days,
            memory.created_at,
            memory.deleted_at,
        )

    async def list_memories(self, user_id: str) -> list[MemoryRecord]:
        rows = await self._require_pool().fetch(
            """SELECT * FROM agent_memories WHERE user_id=$1 AND deleted_at IS NULL
               ORDER BY created_at DESC""",
            user_id,
        )
        return [MemoryRecord.model_validate(dict(row)) for row in rows]

    async def delete_memory(self, memory_id: str, user_id: str) -> bool:
        result = await self._require_pool().execute(
            """UPDATE agent_memories SET deleted_at=$3
               WHERE id=$1 AND user_id=$2 AND deleted_at IS NULL""",
            memory_id,
            user_id,
            utc_now(),
        )
        return str(result) != "UPDATE 0"

    async def list_audit(self, limit: int = 200) -> list[AuditEntry]:
        rows = await self._require_pool().fetch(
            """SELECT mission_id,sequence,event_type,event_hash,previous_receipt_hash,
                      receipt_hash,created_at FROM agent_events
               UNION ALL
               SELECT $2 AS mission_id,sequence,event_type,event_hash,previous_receipt_hash,
                      receipt_hash,created_at FROM agent_control_events
               ORDER BY created_at DESC LIMIT $1""",
            limit,
            CONTROL_MISSION_ID,
        )
        return [AuditEntry.model_validate(dict(row)) for row in rows]

    async def append_control_event(self, event_type: str, payload: dict[str, Any]) -> MissionEvent:
        pool = self._require_pool()
        async with pool.acquire() as connection, connection.transaction():
            last = await connection.fetchrow(
                """SELECT sequence,receipt_hash FROM agent_control_events
                   ORDER BY sequence DESC LIMIT 1 FOR UPDATE"""
            )
            sequence = int(last["sequence"]) + 1 if last else 1
            previous = str(last["receipt_hash"]) if last else "0" * 64
            created_at = utc_now()
            body = {
                "mission_id": CONTROL_MISSION_ID,
                "sequence": sequence,
                "event_type": event_type,
                "payload": payload,
                "created_at": created_at.isoformat(),
            }
            receipt = create_receipt(body, previous)
            event = MissionEvent(
                mission_id=CONTROL_MISSION_ID,
                sequence=sequence,
                event_type=event_type,
                payload=payload,
                created_at=created_at,
                event_hash=receipt.event_hash,
                previous_receipt_hash=receipt.previous_receipt_hash,
                receipt_hash=receipt.receipt_hash,
            )
            await connection.execute(
                """INSERT INTO agent_control_events
                   (sequence,event_type,payload,event_hash,previous_receipt_hash,
                    receipt_hash,created_at) VALUES($1,$2,$3::jsonb,$4,$5,$6,$7)""",
                sequence,
                event_type,
                json.dumps(payload),
                event.event_hash,
                event.previous_receipt_hash,
                event.receipt_hash,
                created_at,
            )
            return event

    async def set_stop(self, active: bool, reason: str) -> None:
        payload = json.dumps({"active": active, "reason": reason})
        await self._require_pool().execute(
            """INSERT INTO agent_control(key,value,updated_at)
               VALUES('safe-stop',$1::jsonb,$2)
               ON CONFLICT(key) DO UPDATE
               SET value=EXCLUDED.value,updated_at=EXCLUDED.updated_at""",
            payload,
            utc_now(),
        )

    async def get_stop(self) -> tuple[bool, str]:
        row = await self._require_pool().fetchrow(
            "SELECT value FROM agent_control WHERE key='safe-stop'"
        )
        if not row:
            return False, ""
        value = _decode_json(row["value"])
        return bool(value.get("active", False)), str(value.get("reason", ""))


def new_memory(user_id: str, mission: Mission, content: str) -> MemoryRecord:
    return MemoryRecord(
        id=new_id("memory"),
        user_id=user_id,
        purpose="user-approved mission result",
        content=content,
        source_mission_id=mission.id,
        retention_days=30,
        created_at=utc_now(),
    )
