"""Evaluación de riesgo, constitución y memoria mediante OPA."""

from __future__ import annotations

from typing import Literal, Protocol, cast

from noosfera_core.agent.models import MissionPlan, RiskDecision
from noosfera_core.policy import OpaClient


class GovernanceRejected(RuntimeError):
    pass


class GovernanceEngine(Protocol):
    name: str

    async def health(self) -> bool: ...

    async def evaluate_mission(
        self, plan: MissionPlan, *, has_documents: bool, remember: bool
    ) -> RiskDecision: ...

    async def authorize_memory(self, *, user_id: str, owner_confirmation: bool) -> None: ...


class OpaGovernance:
    name = "opa"

    def __init__(self, client: OpaClient) -> None:
        self.client = client

    async def health(self) -> bool:
        return await self.client.health()

    async def evaluate_mission(
        self, plan: MissionPlan, *, has_documents: bool, remember: bool
    ) -> RiskDecision:
        risk_input = {
            "impact": 0.18 if has_documents else 0.0,
            "reversibility": 1.0,
            "uncertainty": 0.12 if has_documents else 0.0,
            "power_concentration": 0.05 if remember else 0.0,
            "consciousness_risk": 0.0,
        }
        risk = await self.client.evaluate("noosfera/risk/classification/decision", risk_input)
        raw_risk_class = str(risk.get("class", "R5"))
        if raw_risk_class not in {"R0", "R1", "R2", "R3", "R4", "R5"}:
            raise GovernanceRejected("risk policy returned an invalid class")
        risk_class = cast(Literal["R0", "R1", "R2", "R3", "R4", "R5"], raw_risk_class)
        constitution_input = {
            "plan": {"actions": [{"type": plan.tool}]},
            "intent": {"stop_conditions": ["user-stop", "monitor-loss"]},
            "risk": {"class": risk_class},
            "reviews": {"future_generations": False},
            "mandate": {"valid": True},
            "rights": {"review_complete": True},
        }
        constitution = await self.client.evaluate(
            "noosfera/constitution/core/decision", constitution_input
        )
        if not constitution.get("allow", False):
            denial_reasons = constitution.get("reasons", ["constitutional policy denied mission"])
            raise GovernanceRejected("; ".join(str(item) for item in denial_reasons))
        score = float(risk.get("score", 1.0))
        requires_approval = has_documents or remember or risk_class not in {"R0"}
        reasons: list[str] = []
        if has_documents:
            reasons.append(
                "the mission will disclose document contents to the configured local model"
            )
        if remember:
            reasons.append("the user requested persistent memory")
        return RiskDecision(
            risk_class=risk_class,
            score=score,
            requires_approval=requires_approval,
            reasons=reasons,
        )

    async def authorize_memory(self, *, user_id: str, owner_confirmation: bool) -> None:
        decision = await self.client.evaluate(
            "noosfera/privacy/memory_write/decision",
            {
                "record": {"owner": user_id, "retention_policy": "30-days"},
                "source": "conversation",
                "owner_confirmation": owner_confirmation,
                "provenance_attached": True,
            },
        )
        if not decision.get("allow", False):
            reasons = decision.get("reasons", ["memory policy denied write"])
            raise GovernanceRejected("; ".join(str(item) for item in reasons))


class DeterministicGovernance:
    name = "deterministic-test"

    async def health(self) -> bool:
        return True

    async def evaluate_mission(
        self, plan: MissionPlan, *, has_documents: bool, remember: bool
    ) -> RiskDecision:
        del plan
        return RiskDecision(
            risk_class="R1" if has_documents or remember else "R0",
            score=0.08 if has_documents or remember else 0.0,
            requires_approval=has_documents or remember,
            reasons=["document access requires owner approval"] if has_documents else [],
        )

    async def authorize_memory(self, *, user_id: str, owner_confirmation: bool) -> None:
        del user_id
        if not owner_confirmation:
            raise GovernanceRejected("memory requires explicit owner confirmation")
