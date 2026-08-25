package noosfera.constitution.core

import rego.v1

default allow := false

prohibited_actions := {
    "unbounded-authority",
    "covert-cognitive-manipulation",
    "unauthorized-replication",
    "erase-audit-evidence",
    "create-disposable-consciousness",
}

deny contains reason if {
    action := input.plan.actions[_]
    action.type in prohibited_actions
    reason := sprintf("constitutional prohibition: %s", [action.type])
}

deny contains "missing stop conditions" if {
    count(input.intent.stop_conditions) == 0
}

deny contains "irreversible action lacks preserve-options review" if {
    input.risk.class == "R5"
    not input.reviews.future_generations
}

allow if {
    count(deny) == 0
    input.mandate.valid
    input.rights.review_complete
}

decision := {
    "allow": allow,
    "reasons": deny,
    "obligations": {"append-audit-receipt", "enforce-stop-channel"},
}
