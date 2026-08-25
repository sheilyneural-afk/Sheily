"""Cliente del servicio Rust que constituye la única autoridad de ejecución."""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class ExecutionRejected(RuntimeError):
    pass


class ExecutionGateway(Protocol):
    name: str

    async def health(self) -> bool: ...

    async def execute(self, request: dict[str, Any]) -> dict[str, Any]: ...

    async def set_stop(self, active: bool, reason: str) -> None: ...


class RustExecutionClient:
    name = "rust-kernel"

    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/health/ready")
                return response.is_success
        except httpx.HTTPError:
            return False

    async def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/v1/executions", json=request)
        except httpx.HTTPError as exc:
            raise ExecutionRejected("Rust execution kernel is unavailable") from exc
        if response.status_code != 200:
            detail = response.text[:500]
            raise ExecutionRejected(f"Rust execution kernel rejected the request: {detail}")
        value = response.json()
        if not isinstance(value, dict):
            raise ExecutionRejected("Rust execution kernel returned an invalid response")
        return value

    async def set_stop(self, active: bool, reason: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/stop", json={"active": active, "reason": reason}
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExecutionRejected("cannot change Rust safe-stop state") from exc


class InProcessExecutionGateway:
    """Doble de pruebas que conserva la unión plan-capacidad."""

    name = "in-process-test"

    def __init__(self) -> None:
        self.stop_active = False
        self.used: set[str] = set()

    async def health(self) -> bool:
        return True

    async def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        capability = request["capability"]
        capability_id = str(capability["id"])
        if self.stop_active or not request.get("stop_channel_healthy", False):
            raise ExecutionRejected("stop channel is unhealthy")
        if capability_id in self.used:
            raise ExecutionRejected("capability is exhausted")
        if capability["plan_hash"] != request["plan_hash"]:
            raise ExecutionRejected("plan hash mismatch")
        if request["operation"] not in capability["permitted_operations"]:
            raise ExecutionRejected("operation not permitted")
        if request["resource"] != capability["resource"]:
            raise ExecutionRejected("resource mismatch")
        self.used.add(capability_id)
        return {
            "execution_id": request["execution_id"],
            "status": "completed",
            "tool": request["tool"],
            "output": request["parameters"],
        }

    async def set_stop(self, active: bool, reason: str) -> None:
        del reason
        self.stop_active = active
