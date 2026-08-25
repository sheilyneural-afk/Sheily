"""Orquestador del recorrido intención → plan → autorización → Rust → auditoría."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable
from time import perf_counter
from typing import Any, TypeVar

from noosfera_core.agent.agency import AgencyGateway
from noosfera_core.agent.cognition import CognitionGateway
from noosfera_core.agent.crypto import Ed25519Verifier
from noosfera_core.agent.document_context import build_document_context
from noosfera_core.agent.document_verification import (
    DOCUMENT_VERIFICATION_DOMAIN,
    DocumentVerificationGateway,
)
from noosfera_core.agent.events import EventPublisher
from noosfera_core.agent.execution import ExecutionGateway
from noosfera_core.agent.governance_authority import GovernanceGateway
from noosfera_core.agent.identity import IdentityGateway
from noosfera_core.agent.model_provider import AgentModel
from noosfera_core.agent.models import (
    ApprovalReceipt,
    DocumentVerificationInput,
    Message,
    Mission,
    MissionStatus,
    ModelOutput,
    ResourceBudget,
    new_id,
    utc_now,
)
from noosfera_core.agent.persistence import StateStore, new_memory
from noosfera_core.agent.self_model import SelfModelSnapshot, grounded_self_response
from noosfera_core.hashing import canonical_hash


class MissionConflict(RuntimeError):
    pass


ResultT = TypeVar("ResultT")


class AgentOrchestrator:
    def __init__(
        self,
        *,
        store: StateStore,
        model: AgentModel,
        cognition: CognitionGateway,
        agency: AgencyGateway,
        governance: GovernanceGateway,
        identity: IdentityGateway,
        execution: ExecutionGateway,
        document_verifier: DocumentVerificationGateway,
        audit_signature_verifier: Ed25519Verifier,
        events: EventPublisher,
        max_output_bytes: int,
        model_max_input_chars: int,
        model_document_max_blocks: int,
        model_context_tokens: int,
        model_output_tokens: int,
    ) -> None:
        self.store = store
        self.model = model
        self.cognition = cognition
        self.agency = agency
        self.governance = governance
        self.identity = identity
        self.execution = execution
        self.document_verifier = document_verifier
        self.audit_signature_verifier = audit_signature_verifier
        self.events = events
        self.max_output_bytes = max_output_bytes
        self.model_max_input_chars = model_max_input_chars
        self.model_document_max_blocks = model_document_max_blocks
        self.model_context_tokens = model_context_tokens
        self.model_output_tokens = model_output_tokens
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

    async def _timed(self, mission: Mission, phase: str, operation: Awaitable[ResultT]) -> ResultT:
        started = perf_counter()
        try:
            result = await operation
        except Exception as exc:
            await self._event(
                mission,
                f"phase.{phase}.failed",
                {
                    "duration_ms": round((perf_counter() - started) * 1_000, 3),
                    "error": str(exc)[:500],
                },
            )
            raise
        await self._event(
            mission,
            f"phase.{phase}.completed",
            {"duration_ms": round((perf_counter() - started) * 1_000, 3)},
        )
        return result

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
                cycle = await self._timed(
                    mission,
                    "cognition",
                    self.cognition.deliberate(
                        mission_id=mission.id,
                        user_id=mission.user_id,
                        prompt=mission.prompt,
                        document_ids=mission.document_ids,
                        remember=mission.remember,
                    ),
                )
                await self.events.publish(
                    "cognition.cycle.v1",
                    {
                        "id": cycle.id,
                        "mission_id": mission.id,
                        "observation_hash": cycle.observation_hash,
                        "selected_tool": cycle.selected_tool,
                        "uncertainty": cycle.uncertainty,
                    },
                )
                plan = cycle.plan
                if plan.requires_documents != bool(documents):
                    raise ValueError("cognitive plan does not match attached document scope")
                document_context = [
                    {
                        "id": item.id,
                        "content_hash": item.content_hash,
                        "size_bytes": item.size_bytes,
                    }
                    for item in documents
                ]
                attestation = await self._timed(
                    mission,
                    "agency",
                    self.agency.attest(
                        mission_id=mission.id,
                        user_id=mission.user_id,
                        prompt_hash=canonical_hash(mission.prompt),
                        context_hash=canonical_hash(document_context),
                        plan=plan,
                        budget=ResourceBudget(
                            output_bytes=self.max_output_bytes,
                            model_input_tokens=self.model_context_tokens,
                            model_output_tokens=self.model_output_tokens,
                        ),
                    ),
                )
                await self.events.publish(
                    "agency.plan-attestation.v1",
                    {
                        "mission_id": mission.id,
                        "plan_hash": attestation.plan_hash,
                        "key_id": attestation.key_id,
                        "expiry": attestation.expiry.isoformat(),
                    },
                )
                risk = await self._timed(
                    mission,
                    "governance-evaluation",
                    self.governance.evaluate(
                        attestation, has_documents=bool(documents), remember=mission.remember
                    ),
                )
                mission = mission.model_copy(
                    update={
                        "plan": plan,
                        "plan_hash": attestation.plan_hash,
                        "plan_attestation": attestation,
                        "cognitive_cycle_id": cycle.id,
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
                        "plan_hash": attestation.plan_hash,
                        "agency_key_id": attestation.key_id,
                        "cognitive_cycle_id": cycle.id,
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
                    await self._execute(mission, approval=None)
            except Exception as exc:  # noqa: BLE001
                await self._fail(mission, exc)

    async def approve(
        self,
        mission_id: str,
        user_id: str,
        *,
        access_token: str,
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
            if mission.plan_hash is None:
                raise MissionConflict("mission has no attested plan")
            effective_remember = mission.remember if remember_result is None else remember_result
            receipt = await self.identity.approve(
                token=access_token,
                mission_id=mission.id,
                plan_hash=mission.plan_hash,
                approved=approved,
                remember_result=effective_remember,
                reason=reason,
            )
            if not approved:
                mission = mission.model_copy(update={"approval_receipt": receipt})
                await self.store.save_mission(mission)
                return await self._transition(
                    mission,
                    MissionStatus.REJECTED,
                    "mission.rejected-by-user",
                    {"reason": reason},
                )
            if remember_result is not None:
                mission = mission.model_copy(update={"remember": remember_result})
            mission = mission.model_copy(update={"approval_receipt": receipt})
            mission = await self._transition(
                mission,
                MissionStatus.AUTHORIZED,
                "mission.approved-by-user",
                {"reason": reason, "approval_id": receipt.id, "identity_key_id": receipt.key_id},
            )
            await self.events.publish(
                "identity.approval.v1",
                {
                    "id": receipt.id,
                    "mission_id": receipt.mission_id,
                    "plan_hash": receipt.plan_hash,
                    "approved": receipt.approved,
                    "key_id": receipt.key_id,
                },
            )
            return await self._execute(mission, approval=receipt)

    async def _execute(self, mission: Mission, *, approval: ApprovalReceipt | None) -> Mission:
        if mission.plan is None or mission.plan_hash is None or mission.plan_attestation is None:
            raise MissionConflict("mission has no independently attested plan")
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
        try:
            documents = await self.store.get_documents(mission.document_ids, mission.user_id)
            messages = await self.store.list_messages(mission.conversation_id, mission.user_id)
            history = [{"role": item.role, "content": item.content} for item in messages[:-1]]
            self_model = await self._timed(
                mission, "self-model", self.cognition.inspect_self()
            )
            await self._event(
                mission,
                "mission.self-model-observed",
                {
                    "snapshot_hash": self_model.snapshot_hash,
                    "observed_modules": len(self_model.observed_modules),
                    "verified_modules": len(self_model.verified_modules),
                    "evidence_errors": self_model.evidence_errors,
                },
            )
            await self.events.publish(
                "cognition.self-model.v1",
                {
                    "mission_id": mission.id,
                    "snapshot_hash": self_model.snapshot_hash,
                    "observed_modules": len(self_model.observed_modules),
                    "verified_modules": len(self_model.verified_modules),
                },
            )
            model_output = grounded_self_response(mission.prompt, self_model)
            if model_output is None:
                document_context = (
                    build_document_context(
                        mission.prompt,
                        documents,
                        max_chars=max(
                            10_000,
                            self.model_max_input_chars - len(mission.prompt) - 20_000,
                        ),
                        max_blocks=self.model_document_max_blocks,
                    )
                    if documents
                    else None
                )
                if document_context is not None:
                    await self._event(
                        mission,
                        "mission.evidence-context-built",
                        {
                            "selection_method": document_context.selection_method,
                            "total_blocks": len(document_context.total_block_ids),
                            "analyzed_blocks": len(document_context.analyzed_block_ids),
                            "critical_blocks": len(document_context.critical_block_ids),
                            "missing_artifacts": document_context.missing_artifacts,
                        },
                    )
                model_draft = await self._timed(
                    mission,
                    "language-realization",
                    self.model.respond(
                        mission.prompt,
                        documents=documents,
                        document_context=document_context,
                        history=history,
                        self_model=self_model,
                    ),
                )
                if document_context is not None:
                    model_output = await self._timed(
                        mission,
                        "independent-document-verification",
                        self.document_verifier.verify(
                            DocumentVerificationInput(
                                mission_id=mission.id,
                                prompt=mission.prompt,
                                context=document_context,
                                draft=model_draft,
                            )
                        ),
                    )
                    await self._event(
                        mission,
                        "mission.evidence-bundle-sealed",
                        {
                            "evidence_bundle_hash": (
                                model_output.verification_report.evidence_bundle_hash
                                if model_output.verification_report
                                else None
                            ),
                            "verification_report_hash": (
                                model_output.verification_report.report_hash
                                if model_output.verification_report
                                else None
                            ),
                        },
                    )
                else:
                    model_output = ModelOutput(
                        answer=model_draft.answer,
                        citations=model_draft.citations,
                        claims=model_draft.claims,
                        contradictions=model_draft.contradictions,
                        limitations=model_draft.limitations,
                        unknowns=model_draft.unknowns,
                        assumptions=model_draft.assumptions,
                    )
            else:
                await self._event(
                    mission,
                    "mission.self-answer-grounded",
                    {"snapshot_hash": self_model.snapshot_hash, "llm_used": False},
                )
            self._verify_evidence(model_output, documents, self_model)
            parameters = model_output.model_dump(mode="json")
            grant = await self._timed(
                mission,
                "capability-issuance",
                self.governance.issue_capability(
                    mission.plan_attestation,
                    has_documents=bool(documents),
                    remember=mission.remember,
                    parameters_hash=canonical_hash(parameters),
                    approval=approval,
                ),
            )
            capability = grant.capability
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
                {
                    "capability_id": capability["id"],
                    "expiry": capability["expiry"],
                    "governance_key_id": grant.key_id,
                },
            )
            await self.events.publish(
                "authorization.capability.v1",
                {
                    "id": capability["id"],
                    "mission_id": mission.id,
                    "plan_hash": capability["plan_hash"],
                    "arguments_hash": capability["arguments_hash"],
                    "key_id": grant.key_id,
                    "expiry": capability["expiry"],
                },
            )
            mission = await self._transition(
                mission, MissionStatus.EXECUTING, "mission.executing", {"tool": plan.tool}
            )
            execution_request = {
                "execution_id": new_id("execution"),
                "mission_id": mission.id,
                "user_id": mission.user_id,
                "plan": plan.model_dump(mode="json"),
                "plan_hash": active_plan_hash,
                "capability": capability,
                "capability_signature": grant.signature,
                "capability_key_id": grant.key_id,
                "capability_algorithm": grant.algorithm,
                "tool": plan.tool,
                "operation": plan.operation,
                "resource": plan.resource,
                "parameters": parameters,
                "healthy_monitors": [
                    "urn:noosfera:monitor:model-local",
                    "urn:noosfera:monitor:stop-channel",
                    "urn:noosfera:monitor:capability-ledger",
                ],
                "stop_channel_healthy": True,
            }
            executed = await self._timed(
                mission, "rust-execution", self.execution.execute(execution_request)
            )
            mission = await self._transition(
                mission,
                MissionStatus.VERIFYING,
                "mission.verifying",
                {"execution_id": executed.get("execution_id")},
            )
            output = ModelOutput.model_validate(executed["output"])
            self._verify_evidence(output, documents, self_model)
            assistant_message = Message(
                id=new_id("message"),
                conversation_id=mission.conversation_id,
                role="assistant",
                content=output.answer,
                created_at=utc_now(),
            )
            await self.store.add_message(assistant_message)
            if mission.remember:
                await self.governance.authorize_memory(user_id=mission.user_id, approval=approval)
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

    def _verify_evidence(
        self,
        output: ModelOutput,
        documents: list[Any],
        self_model: SelfModelSnapshot,
    ) -> None:
        allowed = {document.id for document in documents}
        cited = {citation.document_id for citation in output.citations}
        if not cited.issubset(allowed):
            raise ValueError("model cited an unauthorized document")
        if documents and not cited:
            raise ValueError("document report contains no citations")
        if documents:
            blocks = {block.id: block for document in documents for block in document.blocks}
            for citation in output.citations:
                block = blocks.get(citation.block_id)
                if (
                    block is None
                    or block.document_id != citation.document_id
                    or block.version_id != citation.version_id
                    or citation.quote not in block.text
                ):
                    raise ValueError("document report contains an invalid exact citation")
            if output.evidence_bundle is None or output.verification_report is None:
                raise ValueError("document report has no independent verification proof")
            report = output.verification_report
            bundle_hash = canonical_hash(output.evidence_bundle.model_dump(mode="json"))
            if bundle_hash != report.evidence_bundle_hash:
                raise ValueError("evidence bundle hash mismatch")
            report_payload = report.model_dump(mode="json", exclude={"signature"})
            report_body = dict(report_payload)
            report_body.pop("report_hash")
            if canonical_hash(report_body) != report.report_hash:
                raise ValueError("document verification report hash mismatch")
            self.audit_signature_verifier.verify(
                DOCUMENT_VERIFICATION_DOMAIN,
                report_payload,
                report.signature,
                report.key_id,
            )
        allowed_system_evidence = {
            ("urn:noosfera:cognition:self-model", self_model.snapshot_hash)
        }
        supplied_system_evidence = {
            (item.source, item.evidence_hash) for item in output.system_evidence
        }
        if not supplied_system_evidence.issubset(allowed_system_evidence):
            raise ValueError("output cited unauthorized system evidence")
        if output.internal_state_claims:
            raise ValueError("sealed_affective_unobserved_state_not_realized")

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
