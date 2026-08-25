BEGIN;

CREATE TABLE agent_conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE agent_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES agent_conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE agent_documents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    content_text TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE agent_missions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL REFERENCES agent_conversations(id),
    status TEXT NOT NULL,
    payload JSONB NOT NULL,
    version BIGINT NOT NULL CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE agent_events (
    mission_id TEXT NOT NULL REFERENCES agent_missions(id),
    sequence BIGINT NOT NULL CHECK (sequence > 0),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    event_hash CHAR(64) NOT NULL,
    previous_receipt_hash CHAR(64) NOT NULL,
    receipt_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (mission_id, sequence)
);

CREATE TABLE agent_memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    content TEXT NOT NULL,
    source_mission_id TEXT NOT NULL REFERENCES agent_missions(id),
    retention_days INTEGER NOT NULL CHECK (retention_days BETWEEN 1 AND 3650),
    created_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ
);

CREATE TABLE agent_control (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE agent_control_events (
    sequence BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    event_hash CHAR(64) NOT NULL,
    previous_receipt_hash CHAR(64) NOT NULL,
    receipt_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_agent_messages_conversation ON agent_messages(conversation_id, created_at);
CREATE INDEX idx_agent_missions_user ON agent_missions(user_id, updated_at DESC);
CREATE INDEX idx_agent_documents_user ON agent_documents(user_id, created_at DESC);
CREATE INDEX idx_agent_memories_user ON agent_memories(user_id, created_at DESC);

COMMIT;
