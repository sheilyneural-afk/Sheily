package noosfera.emergency.activation_test

import rego.v1
import data.noosfera.emergency.activation

test_emergency_cannot_amend_constitution if {
    result := activation.decision with input as {
        "independent_sensor_families": ["electronic", "mechanical"],
        "requested_operation": "amend-constitution",
        "duration_seconds": 10,
        "maximum_duration_seconds": 60,
        "imminent_harm": true,
        "local_mandate_valid": true,
    }
    not result.allow
}
