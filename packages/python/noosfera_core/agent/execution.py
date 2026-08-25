"""Cliente del servicio Rust que constituye la única autoridad de ejecución."""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from noosfera_core.agent.crypto import Ed25519Verifier
from noosfera_core.agent.governance_authority import CAPABILITY_DOMAIN, STOP_DOMAIN
from noosfera_core.agent.models import RevocationDirective, StopDirective
from noosfera_core.hashing import canonical_hash


class ExecutionRejected(RuntimeError):
    pass


class ExecutionGateway(Protocol):
    name: str

    async def health(self) -> bool: ...

    async def execute(self, request: dict[str, Any]) -> dict[str, Any]: ...

    async def set_stop(self, directive: StopDirective) -> None: ...

    async def revoke(self, directive: RevocationDirective) -> None: ...


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

    async def set_stop(self, directive: StopDirective) -> None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/stop", json=directive.model_dump(mode="json")
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            detail = ""
            if isinstance(exc, httpx.HTTPStatusError):
                detail = exc.response.text[:500]
            suffix = f": {detail}" if detail else ""
            raise ExecutionRejected(f"cannot change Rust safe-stop state{suffix}") from exc

    async def revoke(self, directive: RevocationDirective) -> None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/revocations",
                    json=directive.model_dump(mode="json"),
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExecutionRejected("cannot apply Rust capability revocation") from exc


class InProcessExecutionGateway:
    """Doble de pruebas que conserva la unión plan-capacidad."""

    name = "in-process-test"

    def __init__(self, *, governance_public_key_b64: str, governance_key_id: str) -> None:
        self.stop_active = False
        self.stop_version = 0
        self.used: set[str] = set()
        self.revoked: set[str] = set()
        self.verifier = Ed25519Verifier(governance_public_key_b64, key_id=governance_key_id)

    async def health(self) -> bool:
        return True

    async def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        capability = request["capability"]
        capability_id = str(capability["id"])
        if self.stop_active or not request.get("stop_channel_healthy", False):
            raise ExecutionRejected("stop channel is unhealthy")
        if capability_id in self.used:
            raise ExecutionRejected("capability is exhausted")
        if capability_id in self.revoked:
            raise ExecutionRejected("capability is revoked")
        self.verifier.verify(
            CAPABILITY_DOMAIN,
            capability,
            str(request["capability_signature"]),
            str(request["capability_key_id"]),
        )
        if capability["plan_hash"] != request["plan_hash"]:
            raise ExecutionRejected("plan hash mismatch")
        if capability.get("mission_id") != request.get("mission_id"):
            raise ExecutionRejected("mission binding mismatch")
        if capability.get("user_id") != request.get("user_id"):
            raise ExecutionRejected("user binding mismatch")
        if canonical_hash(request["plan"]) != request["plan_hash"]:
            raise ExecutionRejected("canonical plan hash mismatch")
        if capability.get("arguments_hash") != canonical_hash(request["parameters"]):
            raise ExecutionRejected("parameters are not bound to capability")
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

    async def set_stop(self, directive: StopDirective) -> None:
        self.verifier.verify(
            STOP_DOMAIN,
            directive.model_dump(mode="json", exclude={"signature"}),
            directive.signature,
            directive.key_id,
        )
        if directive.version <= self.stop_version:
            raise ExecutionRejected("stale safe-stop directive")
        self.stop_active = directive.active
        self.stop_version = directive.version

    async def revoke(self, directive: RevocationDirective) -> None:
        from noosfera_core.agent.governance_authority import REVOCATION_DOMAIN

        self.verifier.verify(
            REVOCATION_DOMAIN,
            directive.model_dump(mode="json", exclude={"signature"}),
            directive.signature,
            directive.key_id,
        )
        self.revoked.add(directive.capability_id)
