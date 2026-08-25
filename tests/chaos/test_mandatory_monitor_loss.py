from datetime import UTC, datetime

import pytest
from noosfera_core.capability import CapabilityRejected, authorize_execution
from noosfera_core.hashing import canonical_hash


def test_monitor_loss_blocks_action() -> None:
    plan = {"operation": "test"}
    capability = {
        "id": "urn:noosfera:capability:monitor-test",
        "plan_hash": canonical_hash(plan),
        "resource": "urn:noosfera:actuator:test",
        "permitted_operations": ["test"],
        "not_before": "2026-01-01T00:00:00Z",
        "expiry": "2027-01-01T00:00:00Z",
        "max_uses": 1,
        "delegation": "forbidden",
        "mandatory_monitors": ["urn:noosfera:monitor:required"],
    }
    with pytest.raises(CapabilityRejected, match="mandatory monitor unavailable"):
        authorize_execution(
            plan=plan,
            capability=capability,
            operation="test",
            resource="urn:noosfera:actuator:test",
            healthy_monitors=set(),
            stop_channel_healthy=True,
            now=datetime(2026, 8, 25, tzinfo=UTC),
        )
