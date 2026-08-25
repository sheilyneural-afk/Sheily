package noosfera.authorization.quorum

import rego.v1

default allow := false

distinct_owners := {approval.owner | approval := input.approvals[_]}
distinct_implementations := {approval.implementation | approval := input.approvals[_]}

allow if {
    count(input.approvals) >= input.required_count
    count(distinct_owners) >= input.required_owner_diversity
    count(distinct_implementations) >= input.required_implementation_diversity
    every approval in input.approvals {
        approval.valid
    }
}

decision := {
    "allow": allow,
    "reasons": ["quorum or diversity requirement not satisfied" | not allow],
    "obligations": {"preserve-approval-proofs"},
}
