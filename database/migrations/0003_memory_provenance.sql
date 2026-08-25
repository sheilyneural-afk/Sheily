BEGIN;

CREATE TABLE memory_records (
    record_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    classification TEXT NOT NULL,
    epistemic_status TEXT NOT NULL,
    purpose TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    content_location TEXT,
    retention_policy TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ
);

CREATE TABLE provenance_edges (
    child_record_id TEXT NOT NULL REFERENCES memory_records(record_id),
    parent_record_id TEXT NOT NULL REFERENCES memory_records(record_id),
    transformation TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (child_record_id, parent_record_id)
);

CREATE TABLE deletion_proofs (
    record_id TEXT PRIMARY KEY,
    proof_hash CHAR(64) NOT NULL,
    method TEXT NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL
);

COMMIT;
