BEGIN;

CREATE TABLE federation_packages (
    package_id TEXT PRIMARY KEY,
    source_node TEXT NOT NULL,
    destination_node TEXT NOT NULL,
    protocol TEXT NOT NULL,
    payload_hash CHAR(64) NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    hop_limit INTEGER NOT NULL CHECK (hop_limit >= 0),
    signature JSONB NOT NULL
);

CREATE TABLE treaties (
    treaty_id TEXT NOT NULL,
    version BIGINT NOT NULL,
    state TEXT NOT NULL,
    terms_hash CHAR(64) NOT NULL,
    effective_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    signatures JSONB NOT NULL,
    PRIMARY KEY (treaty_id, version)
);

COMMIT;
