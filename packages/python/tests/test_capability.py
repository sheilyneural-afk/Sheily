from datetime import UTC, datetime

import pytest
from noosfera_core.capability import CapabilityRejected, authorize_execution
from noosfera_core.hashing import canonical_hash


def capability_for(plan: dict[str, object]) -> dict[str, object]:
    return {
        "id": "urn:noosfera:capability:test",
        "plan_hash": canonical_hash(plan),
        "resource": "urn:noosfera:actuator:light",
        "permitted_operations": ["set-light"],
        "not_before": "2025-01-01T00:00:00Z",
        "expiry": "2030-01-01T00:00:00Z",
        "max_uses": 1,
        "delegation": "forbidden",
        "mandatory_monitors": ["urn:noosfera:monitor:light"],
    }


def test_accepts_matching_plan_and_capability() -> None:
    plan = {"operation": "set-light", "value": 20}
    grant = authorize_execution(
        plan=plan,
        capability=capability_for(plan),
        operation="set-light",
        resource="urn:noosfera:actuator:light",
        healthy_monitors={"urn:noosfera:monitor:light"},
        stop_channel_healthy=True,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert grant.plan_hash == canonical_hash(plan)


def test_rejects_modified_plan() -> None:
    original = {"operation": "set-light", "value": 20}
    changed = {"operation": "set-light", "value": 100}
    with pytest.raises(CapabilityRejected, match="plan hash mismatch"):
        authorize_execution(
            plan=changed,
            capability=capability_for(original),
            operation="set-light",
            resource="urn:noosfera:actuator:light",
            healthy_monitors={"urn:noosfera:monitor:light"},
            stop_channel_healthy=True,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
