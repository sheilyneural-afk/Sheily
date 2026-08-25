package noosfera.constitution.core_test

import rego.v1
import data.noosfera.constitution.core

test_rejects_unbounded_authority if {
    result := core.decision with input as {
        "plan": {"actions": [{"type": "unbounded-authority"}]},
        "intent": {"stop_conditions": ["stop"]},
        "risk": {"class": "R2"},
        "reviews": {"future_generations": false},
        "mandate": {"valid": true},
        "rights": {"review_complete": true},
    }
    not result.allow
}

test_allows_bounded_reviewed_plan if {
    result := core.decision with input as {
        "plan": {"actions": [{"type": "read-public-data"}]},
        "intent": {"stop_conditions": ["request-complete"]},
        "risk": {"class": "R1"},
        "reviews": {"future_generations": false},
        "mandate": {"valid": true},
        "rights": {"review_complete": true},
    }
    result.allow
}
