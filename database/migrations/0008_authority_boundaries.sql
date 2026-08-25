BEGIN;

CREATE TABLE cognitive_cycles (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES agent_missions(id),
    user_id TEXT NOT NULL,
    observation_hash CHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_cognitive_cycles_mission
    ON cognitive_cycles(mission_id, created_at DESC);

CREATE TABLE cognitive_beliefs (
    user_id TEXT NOT NULL,
    proposition_hash CHAR(64) NOT NULL,
    belief JSONB NOT NULL,
    source_cycle_id TEXT NOT NULL REFERENCES cognitive_cycles(id),
    first_observed_at TIMESTAMPTZ NOT NULL,
    last_observed_at TIMESTAMPTZ NOT NULL,
    superseded_at TIMESTAMPTZ,
    PRIMARY KEY(user_id, proposition_hash)
);

CREATE INDEX idx_cognitive_beliefs_active
    ON cognitive_beliefs(user_id, last_observed_at DESC)
    WHERE superseded_at IS NULL;

CREATE TABLE governance_grants (
    authorization_key TEXT PRIMARY KEY,
    capability_id TEXT NOT NULL UNIQUE,
    grant_payload JSONB NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE governance_control (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    stop_version BIGINT NOT NULL DEFAULT 0,
    revocation_version BIGINT NOT NULL DEFAULT 0
);

INSERT INTO governance_control(singleton, stop_version, revocation_version) VALUES(TRUE, 0, 0);

CREATE TABLE execution_capability_ledger (
    capability_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    mission_id TEXT NOT NULL REFERENCES agent_missions(id),
    plan_hash CHAR(64) NOT NULL,
    arguments_hash CHAR(64) NOT NULL,
    output_hash CHAR(64) NOT NULL,
    kernel_receipt CHAR(64) NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE execution_control (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    stop_active BOOLEAN NOT NULL,
    stop_version BIGINT NOT NULL,
    reason TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE execution_revocations (
    capability_id TEXT PRIMARY KEY,
    directive_version BIGINT NOT NULL UNIQUE,
    reason TEXT NOT NULL,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO execution_control
    (singleton, stop_active, stop_version, reason, updated_at)
VALUES(TRUE, FALSE, 0, '', NOW());

COMMIT;
