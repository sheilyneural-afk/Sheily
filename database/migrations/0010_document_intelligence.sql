BEGIN;

ALTER TABLE agent_documents ADD COLUMN IF NOT EXISTS normalized_hash CHAR(64);
ALTER TABLE agent_documents ADD COLUMN IF NOT EXISTS version_id TEXT;
ALTER TABLE agent_documents ADD COLUMN IF NOT EXISTS extractor TEXT;
ALTER TABLE agent_documents ADD COLUMN IF NOT EXISTS extractor_version TEXT;

CREATE TABLE IF NOT EXISTS agent_document_blocks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES agent_documents(id),
    version_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal > 0),
    kind TEXT NOT NULL,
    page_number INTEGER,
    section_path JSONB NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    text_hash CHAR(64) NOT NULL,
    content_text TEXT NOT NULL,
    extraction_confidence DOUBLE PRECISION NOT NULL CHECK (
        extraction_confidence >= 0 AND extraction_confidence <= 1
    ),
    epistemic_status TEXT NOT NULL,
    critical BOOLEAN NOT NULL,
    UNIQUE (document_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_agent_document_blocks_document
    ON agent_document_blocks(document_id, ordinal);

CREATE TABLE IF NOT EXISTS audit_document_verifications (
    report_hash CHAR(64) PRIMARY KEY,
    evidence_bundle_hash CHAR(64) NOT NULL,
    key_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TRIGGER audit_document_verifications_append_only
    BEFORE UPDATE OR DELETE ON audit_document_verifications
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

COMMIT;
