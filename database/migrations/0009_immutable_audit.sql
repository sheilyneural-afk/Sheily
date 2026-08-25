BEGIN;

CREATE TABLE audit_anchors (
    id TEXT PRIMARY KEY,
    first_event TEXT NOT NULL,
    last_event TEXT NOT NULL,
    event_count BIGINT NOT NULL CHECK (event_count > 0),
    merkle_root CHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE OR REPLACE FUNCTION reject_append_only_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER agent_events_append_only
    BEFORE UPDATE OR DELETE ON agent_events
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE TRIGGER agent_control_events_append_only
    BEFORE UPDATE OR DELETE ON agent_control_events
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE TRIGGER audit_anchors_append_only
    BEFORE UPDATE OR DELETE ON audit_anchors
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE TRIGGER execution_ledger_append_only
    BEFORE UPDATE OR DELETE ON execution_capability_ledger
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

CREATE TRIGGER execution_revocations_append_only
    BEFORE UPDATE OR DELETE ON execution_revocations
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

COMMIT;
