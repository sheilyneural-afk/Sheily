BEGIN;

CREATE TABLE capabilities (
    capability_id TEXT PRIMARY KEY,
    issuer_id TEXT NOT NULL,
    holder_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    plan_hash CHAR(64) NOT NULL,
    permitted_operations JSONB NOT NULL,
    bounds JSONB NOT NULL,
    not_before TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    max_uses INTEGER NOT NULL CHECK (max_uses > 0),
    uses_consumed INTEGER NOT NULL DEFAULT 0 CHECK (uses_consumed >= 0),
    delegation TEXT NOT NULL CHECK (delegation IN ('forbidden', 'bounded')),
    quorum_proof_id TEXT NOT NULL,
    signature JSONB NOT NULL,
    CHECK (expires_at > not_before),
    CHECK (uses_consumed <= max_uses)
);

CREATE TABLE capability_revocations (
    capability_id TEXT PRIMARY KEY REFERENCES capabilities(capability_id),
    reason TEXT NOT NULL,
    revoked_at TIMESTAMPTZ NOT NULL,
    authority_id TEXT NOT NULL,
    signature JSONB NOT NULL
);

CREATE INDEX capability_active_lookup ON capabilities (resource_id, expires_at);

COMMIT;
