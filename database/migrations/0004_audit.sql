BEGIN;

CREATE TABLE audit_receipts (
    receipt_hash CHAR(64) PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    event_hash CHAR(64) NOT NULL,
    previous_receipt_hash CHAR(64) NOT NULL,
    classification TEXT NOT NULL,
    witness_id TEXT NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL,
    signature JSONB NOT NULL
);

CREATE TABLE dissent_records (
    dissent_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    claim_hash CHAR(64) NOT NULL,
    reconsideration_conditions JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE incidents (
    incident_id TEXT PRIMARY KEY,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,
    evidence_location TEXT NOT NULL
);

COMMIT;
