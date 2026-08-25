"""Cliente mínimo de OPA; falla de forma cerrada."""

from __future__ import annotations

from typing import Any

import httpx


class PolicyUnavailable(RuntimeError):
    pass


class OpaClient:
    def __init__(self, base_url: str, timeout_seconds: float = 2.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def evaluate(self, package_path: str, value: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/v1/data/{package_path.strip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json={"input": value})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PolicyUnavailable("policy engine unavailable") from exc
        payload = response.json()
        result = payload.get("result")
        if not isinstance(result, dict):
            raise PolicyUnavailable("policy engine returned no structured decision")
        return result
