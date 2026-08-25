package noosfera.authorization.capability_test

import rego.v1
import data.noosfera.authorization.capability

base_input := {
    "now": "2300-01-01T00:00:00Z",
    "plan": {"hash": "abc"},
    "operation": "set-light",
    "stop_channel_healthy": true,
    "monitor_health": {"monitor-1": true},
    "capability": {
        "plan_hash": "abc",
        "not_before": "2299-12-31T00:00:00Z",
        "expiry": "2300-01-02T00:00:00Z",
        "permitted_operations": ["set-light"],
        "mandatory_monitors": ["monitor-1"],
        "remaining_uses": 1,
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
