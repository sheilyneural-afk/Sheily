package noosfera.privacy.memory_read_test

import rego.v1
import data.noosfera.privacy.memory_read

test_rejects_cognitive_data_without_explicit_consent if {
    result := memory_read.decision with input as {
        "request": {"purpose": "care", "view": "summary", "requester": "agent-1"},
        "consent": {"purpose": "care", "allowed_views": ["summary"], "grantee": "agent-1", "revoked": false, "explicit": false},
        "record": {"classification": "cognitive"},
    }
    not result.allow
}
