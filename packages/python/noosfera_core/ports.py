"""Puertos que aíslan capacidades externas de los dominios de Noosfera."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class ModelProvider(Protocol):
    async def infer(
        self, request: dict[str, Any], *, output_schema: dict[str, Any]
    ) -> dict[str, Any]: ...


class SensorProvider(Protocol):
    async def observe(self, sensor_id: str) -> dict[str, Any]: ...


class ActuatorProvider(Protocol):
    async def manifest(self) -> dict[str, Any]: ...

    async def execute(self, command: dict[str, Any]) -> dict[str, Any]: ...

    async def safe_stop(self, reason: str, target_state: str) -> dict[str, Any]: ...


class PolicyProvider(Protocol):
    async def evaluate(self, policy_id: str, value: dict[str, Any]) -> dict[str, Any]: ...


class AuditLedger(Protocol):
    async def append(self, event: dict[str, Any]) -> dict[str, Any]: ...


class ObjectStore(Protocol):
    async def put(self, namespace: str, content: bytes) -> str: ...

    async def get(self, location: str) -> bytes: ...

    async def delete(self, location: str) -> str: ...


class SigningProvider(Protocol):
    async def sign(self, key_reference: str, content: bytes) -> dict[str, str]: ...

    async def verify(self, signature: dict[str, str], content: bytes) -> bool: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class FederationTransport(Protocol):
    async def enqueue(self, package: dict[str, Any]) -> str: ...

    async def receive(self) -> dict[str, Any] | None: ...
