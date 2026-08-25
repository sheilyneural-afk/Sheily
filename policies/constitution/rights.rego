package noosfera.constitution.rights

import rego.v1

default allow := false

protected_rights := {
    "integrity",
    "cognitive-liberty",
    "identity-sovereignty",
    "meaningful-consent",
    "appeal",
    "exit",
}

violations contains right if {
    right := input.affected_rights[_]
    right in protected_rights
    not input.safeguards[right]
}

allow if {
    count(violations) == 0
}

decision := {
    "allow": allow,
    "reasons": [sprintf("unsafeguarded right: %s", [right]) | right := violations[_]],
    "obligations": {"preserve-appeal-path"},
}
