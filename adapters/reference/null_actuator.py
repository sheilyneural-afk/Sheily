from __future__ import annotations

from typing import Any


class NullActuator:
    """Actuador de referencia que registra rechazo y nunca produce efectos."""

    async def manifest(self) -> dict[str, Any]:
        return {
            "identity": "urn:noosfera:actuator:null",
            "class": "digital-read",
            "operations": ["dry-run"],
            "safe_states": ["no-effect"],
            "stop_latency_ms": 0,
        }

    async def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        return {"status": "no-effect", "accepted": False, "command_hash_required": True}

    async def safe_stop(self, reason: str, target_state: str) -> dict[str, Any]:
        return {"status": "safe", "reason": reason, "target_state": target_state}
