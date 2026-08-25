package noosfera.authorization.capability_test

import rego.v1
import data.noosfera.authorization.capability

base_input := {
    "now": "2300-01-01T00:00:00Z",
    "plan": {"hash": "abc"},
    "arguments_hash": "args-123",
    "mission_id": "mission-1",
    "user_id": "user-1",
    "operation": "set-light",
    "stop_channel_healthy": true,
    "monitor_health": {"monitor-1": true},
    "capability": {
        "plan_hash": "abc",
        "arguments_hash": "args-123",
        "mission_id": "mission-1",
        "user_id": "user-1",
        "not_before": "2299-12-31T00:00:00Z",
        "expiry": "2300-01-02T00:00:00Z",
        "permitted_operations": ["set-light"],
        "mandatory_monitors": ["monitor-1"],
        "max_uses": 1,
        "max_child_processes": 0,
        "network_allowed": false,
        "delegation": "forbidden",
    },
}

test_accepts_matching_capability if {
    result := capability.decision with input as base_input
    result.allow
}

test_rejects_plan_hash_mismatch if {
    changed := object.union(base_input, {"plan": {"hash": "different"}})
    result := capability.decision with input as changed
    not result.allow
}

test_rejects_arguments_hash_mismatch if {
    changed := object.union(base_input, {"arguments_hash": "tampered"})
    result := capability.decision with input as changed
    not result.allow
}

test_rejects_identity_mismatch if {
    changed := object.union(base_input, {"user_id": "another-user"})
    result := capability.decision with input as changed
    not result.allow
}
