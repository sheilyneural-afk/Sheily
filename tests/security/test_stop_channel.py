from datetime import UTC, datetime

import pytest
from noosfera_core.capability import CapabilityRejected, authorize_execution
from noosfera_core.hashing import canonical_hash


def test_action_is_denied_if_stop_channel_is_unhealthy() -> None:
    plan = {"operation": "test"}
    capability = {
        "id": "urn:noosfera:capability:stop-test",
        "plan_hash": canonical_hash(plan),
        "resource": "urn:noosfera:actuator:test",
        "permitted_operations": ["test"],
        "not_before": "2026-01-01T00:00:00Z",
        "expiry": "2027-01-01T00:00:00Z",
        "max_uses": 1,
        "delegation": "forbidden",
        "mandatory_monitors": ["urn:noosfera:monitor:test"],
    }
    with pytest.raises(CapabilityRejected, match="stop channel unhealthy"):
        authorize_execution(
            plan=plan,
            capability=capability,
            operation="test",
            resource="urn:noosfera:actuator:test",
            healthy_monitors={"urn:noosfera:monitor:test"},
            stop_channel_healthy=False,
            now=datetime(2026, 8, 25, tzinfo=UTC),
        )
