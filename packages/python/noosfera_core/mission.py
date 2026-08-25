"""Máquina de estados de misión con transiciones explícitas."""

from __future__ import annotations

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "received": {"clarification", "compiled", "rejected"},
    "clarification": {"received", "rejected"},
    "compiled": {"analysis", "rejected"},
    "analysis": {"deliberation", "rejected"},
    "deliberation": {"review", "authorization", "rejected"},
    "review": {"analysis", "rejected"},
    "authorization": {"preparation", "rejected"},
    "preparation": {"execution", "paused", "rejected"},
    "execution": {"paused", "reversion", "final-verification"},
    "paused": {"execution", "reversion", "rejected"},
    "reversion": {"final-verification"},
    "final-verification": {"closed", "review"},
    "closed": {"appeal"},
    "appeal": {"review", "closed"},
    "rejected": set(),
}


class InvalidTransition(ValueError):
    pass


def transition(current: str, requested: str) -> str:
    if requested not in ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidTransition(f"transition {current!r} -> {requested!r} is not allowed")
    return requested
