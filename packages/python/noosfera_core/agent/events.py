"""Publicación de eventos en NATS con una alternativa explícita para pruebas."""

from __future__ import annotations

import json
from typing import Any, Protocol


class EventPublisher(Protocol):
    name: str

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def health(self) -> bool: ...

    async def publish(self, subject: str, payload: dict[str, Any]) -> None: ...


class NullEventPublisher:
    name = "disabled-test"

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def health(self) -> bool:
        return True

    async def publish(self, subject: str, payload: dict[str, Any]) -> None:
        del subject, payload


class NatsEventPublisher:
    name = "nats"

    def __init__(self, url: str) -> None:
        self.url = url
        self._client: Any = None

    async def connect(self) -> None:
        import nats

        self._client = await nats.connect(self.url, connect_timeout=2, max_reconnect_attempts=10)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.drain()

    async def health(self) -> bool:
        return bool(self._client is not None and self._client.is_connected)

    async def publish(self, subject: str, payload: dict[str, Any]) -> None:
        if self._client is None:
            raise RuntimeError("NATS publisher is not connected")
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        await self._client.publish(subject, encoded)
