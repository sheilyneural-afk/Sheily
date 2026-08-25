"""Orquestador del recorrido intención → plan → autorización → Rust → auditoría."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import timedelta
from typing import Any

from noosfera_core.agent.auth import sign_capability
from noosfera_core.agent.events import EventPublisher
from noosfera_core.agent.execution import ExecutionGateway
from noosfera_core.agent.governance import GovernanceEngine
from noosfera_core.agent.model_provider import AgentModel
from noosfera_core.agent.models import (
    Message,
    Mission,
    MissionStatus,
    ModelOutput,
    new_id,
    utc_now,
)
from noosfera_core.agent.persistence import StateStore, new_memory
from noosfera_core.hashing import canonical_hash


class MissionConflict(RuntimeError):
    pass


class AgentOrchestrator:
    def __init__(
        self,
        *,
        store: StateStore,
        model: AgentModel,
        governance: GovernanceEngine,
        execution: ExecutionGateway,
        events: EventPublisher,
        capability_secret: str,
        capability_ttl_seconds: int,
        max_output_bytes: int,
    ) -> None:
        self.store = store
        self.model = model
        self.governance = governance
        self.execution = execution
        self.events = events
        self.capability_secret = capability_secret
        self.capability_ttl_seconds = capability_ttl_seconds
        self.max_output_bytes = max_output_bytes
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def _event(self, mission: Mission, event_type: str, payload: dict[str, Any]) -> None:
        event = await self.store.append_event(mission.id, event_type, payload)
        await self.events.publish(
            "mission.event.v1",
            {
                "mission_id": mission.id,
                "sequence": event.sequence,
                "event_type": event_type,
                "receipt_hash": event.receipt_hash,
                "created_at": event.created_at.isoformat(),
            },
        )

    async def _transition(
        self, mission: Mission, status: MissionStatus, event_type: str, payload: dict[str, Any]
    ) -> Mission:
        updated = mission.model_copy(
            update={
                "status": status,
                "version": mission.version + 1,
                "updated_at": utc_now(),
            }
        )
        await self.store.save_mission(updated)
        await self._event(updated, event_type, payload)
        return updated

    async def plan(self, mission_id: str, user_id: str) -> None:
        async with self._locks[mission_id]:
            mission = await self.store.get_mission(mission_id, user_id)
            if mission is None or mission.status != MissionStatus.RECEIVED:
                return
            try:
                mission = await self._transition(
                    mission, MissionStatus.PLANNING, "mission.planning", {}
                )
                documents = await self.store.get_documents(mission.document_ids, user_id)
                if len(documents) != len(set(mission.document_ids)):
                    raise ValueError("one or more documents are missing or unauthorized")
                plan = await self.model.plan(mission.prompt, has_documents=bool(documents))
                if plan.requires_documents != bool(documents):
                    raise ValueError("model plan does not match attached document scope")
                plan_hash = canonical_hash(plan.model_dump(mode="json"))
                risk = await self.governance.evaluate_mission(
                    plan, has_documents=bool(documents), remember=mission.remember
                )
                mission = mission.model_copy(
                    update={
                        "plan": plan,
                        "plan_hash": plan_hash,
                        "risk": risk,
                        "version": mission.version + 1,
                        "updated_at": utc_now(),
                    }
                )
                await self.store.save_mission(mission)
                await self._event(
                    mission,
                    "mission.plan-ready",
                    {
                        "plan_hash": plan_hash,
                        "tool": plan.tool,
                        "risk_class": risk.risk_class,
                        "requires_approval": risk.requires_approval,
                    },
                )
                if risk.requires_approval:
                    await self._transition(
                        mission,
                        MissionStatus.AWAITING_APPROVAL,
                        "mission.approval-required",
                        {"reasons": risk.reasons},
                    )
                else:
                    await self._execute(mission)
            except Exception as exc:  # noqa: BLE001
                await self._fail(mission, exc)

    async def approve(
        self,
        mission_id: str,
        user_id: str,
        *,
        approved: bool,
        remember_result: bool | None,
        reason: str,
    ) -> Mission:
        async with self._locks[mission_id]:
            mission = await self.store.get_mission(mission_id, user_id)
            if mission is None:
                raise KeyError(mission_id)
            if mission.status != MissionStatus.AWAITING_APPROVAL:
                raise MissionConflict("mission is not waiting for approval")
            if not approved:
                return await self._transition(
                    mission,
                    MissionStatus.REJECTED,
                    "mission.rejected-by-user",
                    {"reason": reason},
                )
            if remember_result is not None:
                mission = mission.model_copy(update={"remember": remember_result})
                await self.store.save_mission(mission)
            await self._event(mission, "mission.approved-by-user", {"reason": reason})
            return await self._execute(mission)

    async def _execute(self, mission: Mission) -> Mission:
        if mission.plan is None or mission.plan_hash is None:
            raise MissionConflict("mission has no validated plan")
        plan = mission.plan
        active_plan_hash = mission.plan_hash
        stopped, stop_reason = await self.store.get_stop()
        if stopped:
            return await self._transition(
                mission,
                MissionStatus.STOPPED,
                "mission.stopped",
                {"reason": stop_reason or "safe stop active"},
            )
        now = utc_now()
        capability = {
            "id": new_id("capability"),
            "issuer": "urn:noosfera:service:governance",
            "holder": "urn:noosfera:service:experience",
            "resource": plan.resource,
            "permitted_operations": [plan.operation],
            "plan_hash": active_plan_hash,
            "bounds": {
                "output_bytes": {"unit": "bytes", "maximum": self.max_output_bytes},
                "wall_time": {"unit": "seconds", "maximum": 30},
            },
            "preconditions": ["owner-authorized", "local-model-only"],
            "mandatory_monitors": [
                "urn:noosfera:monitor:model-local",
                "urn:noosfera:monitor:stop-channel",
            ],
            "stop_conditions": ["user-stop", "monitor-loss", "budget-exhausted"],
            "not_before": now.isoformat().replace("+00:00", "Z"),
            "expiry": (now + timedelta(seconds=self.capability_ttl_seconds))
            .isoformat()
            .replace("+00:00", "Z"),
            "max_uses": 1,
            "delegation": "forbidden",
            "quorum_proof": f"urn:noosfera:approval:{mission.id}",
        }
        capability_signature = sign_capability(capability, self.capability_secret)
        mission = mission.model_copy(
            update={
                "status": MissionStatus.AUTHORIZED,
                "capability_id": capability["id"],
                "version": mission.version + 1,
                "updated_at": utc_now(),
            }
        )
        await self.store.save_mission(mission)
        await self._event(
            mission,
            "mission.capability-issued",
            {"capability_id": capability["id"], "expiry": capability["expiry"]},
        )
        mission = await self._transition(
            mission, MissionStatus.EXECUTING, "mission.executing", {"tool": plan.tool}
        )
        try:
            documents = await self.store.get_documents(mission.document_ids, mission.user_id)
            messages = await self.store.list_messages(mission.conversation_id, mission.user_id)
            history = [{"role": item.role, "content": item.content} for item in messages[:-1]]
            model_output = await self.model.respond(
                mission.prompt, documents=documents, history=history
            )
            self._verify_evidence(model_output, documents)
            execution_request = {
                "execution_id": new_id("execution"),
                "plan": plan.model_dump(mode="json"),
                "plan_hash": active_plan_hash,
                "capability": capability,
                "capability_signature": capability_signature,
                "tool": plan.tool,
                "operation": plan.operation,
                "resource": plan.resource,
                "parameters": model_output.model_dump(mode="json"),
                "healthy_monitors": [
                    "urn:noosfera:monitor:model-local",
                    "urn:noosfera:monitor:stop-channel",
                ],
                "stop_channel_healthy": True,
            }
            executed = await self.execution.execute(execution_request)
            mission = await self._transition(
                mission,
                MissionStatus.VERIFYING,
                "mission.verifying",
                {"execution_id": executed.get("execution_id")},
            )
            output = ModelOutput.model_validate(executed["output"])
            self._verify_evidence(output, documents)
            assistant_message = Message(
                id=new_id("message"),
                conversation_id=mission.conversation_id,
                role="assistant",
                content=output.answer,
                created_at=utc_now(),
            )
            await self.store.add_message(assistant_message)
            if mission.remember:
                await self.governance.authorize_memory(
                    user_id=mission.user_id, owner_confirmation=True
                )
                await self.store.save_memory(new_memory(mission.user_id, mission, output.answer))
                await self._event(mission, "memory.written", {"retention_days": 30})
            completed = mission.model_copy(
                update={
                    "status": MissionStatus.COMPLETED,
                    "result": output,
                    "version": mission.version + 1,
                    "updated_at": utc_now(),
                }
            )
            await self.store.save_mission(completed)
            await self._event(
                completed,
                "mission.completed",
                {
                    "citations": [item.document_id for item in output.citations],
                    "remembered": completed.remember,
                },
            )
            return completed
        except Exception as exc:  # noqa: BLE001
            return await self._fail(mission, exc)

    @staticmethod
    def _verify_evidence(output: ModelOutput, documents: list[Any]) -> None:
        allowed = {document.id for document in documents}
        cited = {citation.document_id for citation in output.citations}
        if not cited.issubset(allowed):
            raise ValueError("model cited an unauthorized document")
        if documents and not cited:
            raise ValueError("document report contains no citations")

    async def _fail(self, mission: Mission, exc: Exception) -> Mission:
        failed = mission.model_copy(
            update={
                "status": MissionStatus.FAILED,
                "error": str(exc)[:1_000],
                "version": mission.version + 1,
                "updated_at": utc_now(),
            }
        )
        await self.store.save_mission(failed)
        await self._event(failed, "mission.failed", {"error": failed.error})
        return failed
