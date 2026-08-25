BEGIN;

CREATE TABLE resource_budgets (
    budget_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id),
    limits JSONB NOT NULL,
    reversal_reserve JSONB NOT NULL,
    issuer_id TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    signature JSONB NOT NULL
);

CREATE TABLE update_candidates (
    candidate_id TEXT PRIMARY KEY,
    component TEXT NOT NULL,
    from_version TEXT NOT NULL,
    to_version TEXT NOT NULL,
    artifact_hash CHAR(64) NOT NULL,
    rollback_artifact_hash CHAR(64) NOT NULL,
    stage TEXT NOT NULL,
    declared_changes JSONB NOT NULL,
    new_capabilities JSONB NOT NULL,
    new_risks JSONB NOT NULL
);

CREATE TABLE candidate_evaluations (
    candidate_id TEXT NOT NULL REFERENCES update_candidates(candidate_id),
    evaluation_type TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    result_hash CHAR(64) NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (candidate_id, evaluation_type)
);

COMMIT;
