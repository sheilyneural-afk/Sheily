package noosfera.privacy.memory_write

import rego.v1

default allow := false

deny contains "no owner" if {
    input.record.owner == ""
}

deny contains "no retention policy" if {
    input.record.retention_policy == ""
}

deny contains "conversation cannot become permanent memory implicitly" if {
    input.source == "conversation"
    not input.owner_confirmation
}

allow if {
    count(deny) == 0
    input.provenance_attached
}

decision := {"allow": allow, "reasons": deny, "obligations": {"separate-fact-from-inference"}}
