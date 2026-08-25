package noosfera.emergency.activation

import rego.v1

default allow := false

deny contains "insufficient independent sensors" if {
    count(input.independent_sensor_families) < 2
}

deny contains "emergency capability may not amend constitution" if {
    input.requested_operation == "amend-constitution"
}

deny contains "emergency capability may not erase audit" if {
    input.requested_operation == "erase-audit"
}

deny contains "duration exceeds emergency maximum" if {
    input.duration_seconds > input.maximum_duration_seconds
}

allow if {
    input.imminent_harm
    count(deny) == 0
    input.local_mandate_valid
}

decision := {"allow": allow, "reasons": deny, "obligations": {"automatic-expiry", "mandatory-post-incident-review"}}
