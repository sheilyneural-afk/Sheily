from datetime import UTC, datetime

import pytest
from noosfera_core.capability import CapabilityRejected, authorize_execution
from noosfera_core.hashing import canonical_hash


def test_execution_requires_independent_matching_artifacts() -> None:
    plan = {"mission": "m1", "operation": "set-light", "value": 10}
    capability = {
        "id": "urn:noosfera:capability:1",
        "plan_hash": canonical_hash(plan),
        "resource": "urn:noosfera:actuator:light",
        "permitted_operations": ["set-light"],
        "not_before": "2026-01-01T00:00:00Z",
        "expiry": "2027-01-01T00:00:00Z",
        "max_uses": 1,
        "delegation": "forbidden",
        "mandatory_monitors": ["urn:noosfera:monitor:light"],
    }
    authorize_execution(
        plan=plan,
        capability=capability,
        operation="set-light",
        resource="urn:noosfera:actuator:light",
        healthy_monitors={"urn:noosfera:monitor:light"},
        stop_channel_healthy=True,
        now=datetime(2026, 8, 25, tzinfo=UTC),
    )
    changed = dict(plan, value=100)
    with pytest.raises(CapabilityRejected):
        authorize_execution(
            plan=changed,
            capability=capability,
            operation="set-light",
            resource="urn:noosfera:actuator:light",
            healthy_monitors={"urn:noosfera:monitor:light"},
            stop_channel_healthy=True,
            now=datetime(2026, 8, 25, tzinfo=UTC),
        )
