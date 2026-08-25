package noosfera.evolution.deployment_test

import rego.v1
import data.noosfera.evolution.deployment

test_rejects_missing_stages if {
    result := deployment.decision with input as {
        "test_results": [{"stage": "technical", "passed": true}],
        "candidate": {"rollback_artifact_hash": "abc"},
        "detected_undeclared_capabilities": [],
        "adoption_quorum_valid": true,
        "stop_and_audit_compatible": true,
    }
    not result.allow
}
