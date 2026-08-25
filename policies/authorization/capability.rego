package noosfera.authorization.capability

import rego.v1

default allow := false

deny contains "plan hash mismatch" if {
    input.plan.hash != input.capability.plan_hash
}

deny contains "arguments hash mismatch" if {
    input.arguments_hash != input.capability.arguments_hash
}

deny contains "mission mismatch" if {
    input.mission_id != input.capability.mission_id
}

deny contains "user mismatch" if {
    input.user_id != input.capability.user_id
}

deny contains "capability expired" if {
    time.parse_rfc3339_ns(input.now) >= time.parse_rfc3339_ns(input.capability.expiry)
}

deny contains "capability not active yet" if {
    time.parse_rfc3339_ns(input.now) < time.parse_rfc3339_ns(input.capability.not_before)
}

deny contains "operation not permitted" if {
    not input.operation in input.capability.permitted_operations
}

deny contains "network access forbidden" if {
    input.capability.network_allowed
}

deny contains "stop channel unhealthy" if {
    not input.stop_channel_healthy
}

deny contains "mandatory monitor unavailable" if {
    monitor := input.capability.mandatory_monitors[_]
    not input.monitor_health[monitor]
}

allow if {
    count(deny) == 0
    input.capability.max_uses == 1
    input.capability.max_child_processes == 0
    input.capability.delegation == "forbidden"
}

decision := {"allow": allow, "reasons": deny, "obligations": {"consume-one-use", "append-audit-receipt"}}
