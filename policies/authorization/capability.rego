package noosfera.authorization.capability

import rego.v1

default allow := false

deny contains "plan hash mismatch" if {
    input.plan.hash != input.capability.plan_hash
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

deny contains "stop channel unhealthy" if {
    not input.stop_channel_healthy
}

deny contains "mandatory monitor unavailable" if {
    monitor := input.capability.mandatory_monitors[_]
    not input.monitor_health[monitor]
}

allow if {
    count(deny) == 0
    input.capability.remaining_uses > 0
    input.capability.delegation == "forbidden"
}

decision := {"allow": allow, "reasons": deny, "obligations": {"consume-one-use", "append-audit-receipt"}}
