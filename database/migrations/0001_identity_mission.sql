BEGIN;

CREATE TABLE identities (
    identity_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('active', 'suspended', 'disputed', 'retired')),
    assurance_level TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE delegations (
    delegation_id TEXT PRIMARY KEY,
    grantor_id TEXT NOT NULL REFERENCES identities(identity_id),
    grantee_id TEXT NOT NULL REFERENCES identities(identity_id),
    scope JSONB NOT NULL,
    not_before TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    CHECK (expires_at > not_before)
);

CREATE TABLE consent_receipts (
    consent_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES identities(identity_id),
    grantee_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    allowed_views JSONB NOT NULL,
    explicit BOOLEAN NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE missions (
    mission_id TEXT PRIMARY KEY,
    intent_contract_id TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    version BIGINT NOT NULL CHECK (version > 0),
    last_event_id TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

COMMIT;
