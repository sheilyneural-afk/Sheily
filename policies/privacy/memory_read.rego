package noosfera.privacy.memory_read

import rego.v1

default allow := false

deny contains "purpose mismatch" if {
    input.request.purpose != input.consent.purpose
}

deny contains "request exceeds consented view" if {
    not input.request.view in input.consent.allowed_views
}

deny contains "consent revoked" if {
    input.consent.revoked
}

deny contains "cognitive data requires explicit consent" if {
    input.record.classification == "cognitive"
    not input.consent.explicit
}

allow if {
    count(deny) == 0
    input.request.requester == input.consent.grantee
}

decision := {"allow": allow, "reasons": deny, "obligations": {"expire-derived-view", "audit-access-metadata"}}
