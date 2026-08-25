from __future__ import annotations

from typing import Any


class DeterministicModel:
    """Devuelve una respuesta fija; no pretende implementar cognición real."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    async def infer(
        self, request: dict[str, Any], *, output_schema: dict[str, Any]
    ) -> dict[str, Any]:
        del request, output_schema
        return dict(self.response)
