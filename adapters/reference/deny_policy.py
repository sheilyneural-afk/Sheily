from __future__ import annotations

from typing import Any


class DenyPolicy:
    async def evaluate(self, policy_id: str, value: dict[str, Any]) -> dict[str, Any]:
        del value
        return {
            "allow": False,
            "reasons": [f"reference policy denies {policy_id}"],
            "obligations": [],
        }
