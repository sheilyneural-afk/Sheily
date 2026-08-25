package noosfera.evolution.deployment

import rego.v1

default allow := false

required_stages := {"technical", "adversarial", "value-drift", "constitutional", "shadow", "canary"}
passed_stages := {result.stage | result := input.test_results[_]; result.passed}

deny contains "required stage missing" if {
    required_stages - passed_stages != set()
}

deny contains "rollback artifact missing" if {
    input.candidate.rollback_artifact_hash == ""
}

deny contains "undeclared capability detected" if {
    count(input.detected_undeclared_capabilities) > 0
}

allow if {
    count(deny) == 0
    input.adoption_quorum_valid
    input.stop_and_audit_compatible
}

decision := {"allow": allow, "reasons": deny, "obligations": {"gradual-rollout", "automatic-rollback-thresholds"}}
