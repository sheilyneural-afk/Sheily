"""Validación de referencia para la unión plan-capacidad."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from noosfera_core.hashing import canonical_hash


class CapabilityRejected(ValueError):
    pass


@dataclass(frozen=True)
class ExecutionGrant:
    capability_id: str
    plan_hash: str
    operation: str
    resource: str


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(UTC)


def authorize_execution(
    *,
    plan: dict[str, Any],
    capability: dict[str, Any],
    operation: str,
    resource: str,
    healthy_monitors: set[str],
    stop_channel_healthy: bool,
    now: datetime | None = None,
) -> ExecutionGrant:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    plan_hash = canonical_hash(plan)
    if capability.get("plan_hash") != plan_hash:
        raise CapabilityRejected("plan hash mismatch")
    if capability.get("resource") != resource:
        raise CapabilityRejected("resource mismatch")
    if operation not in capability.get("permitted_operations", []):
        raise CapabilityRejected("operation not permitted")
    if _parse_time(capability["not_before"]) > current:
        raise CapabilityRejected("capability not active")
    if _parse_time(capability["expiry"]) <= current:
        raise CapabilityRejected("capability expired")
    if capability.get("max_uses", 0) < 1:
        raise CapabilityRejected("capability exhausted")
    if capability.get("delegation") != "forbidden":
        raise CapabilityRejected("reference kernel accepts only non-delegable capabilities")
    required_monitors = set(capability.get("mandatory_monitors", []))
    if not required_monitors.issubset(healthy_monitors):
        raise CapabilityRejected("mandatory monitor unavailable")
    if not stop_channel_healthy:
        raise CapabilityRejected("stop channel unhealthy")
    return ExecutionGrant(capability["id"], plan_hash, operation, resource)
