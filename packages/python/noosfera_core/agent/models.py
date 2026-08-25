"""Modelos canónicos del agente funcional local-first."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(kind: str) -> str:
    return f"urn:noosfera:{kind}:{uuid4()}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MissionStatus(StrEnum):
    RECEIVED = "received"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting-approval"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    STOPPED = "stopped"


TERMINAL_STATUSES = {
    MissionStatus.COMPLETED,
    MissionStatus.REJECTED,
    MissionStatus.FAILED,
    MissionStatus.STOPPED,
}


class LoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)


class TokenResponse(StrictModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 -- OAuth token kind, not a secret
    expires_in: int
    user_id: str
    role: str


class Principal(StrictModel):
    user_id: str
    username: str
    role: Literal["user", "operator", "admin"]


class Conversation(StrictModel):
    id: str
    user_id: str
    title: str
    created_at: datetime


class ConversationCreate(StrictModel):
    title: str = Field(default="Nueva conversación", min_length=1, max_length=200)


class Message(StrictModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class MessageCreate(StrictModel):
    content: str = Field(min_length=1, max_length=20_000)
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    remember: bool = False


class DocumentRecord(StrictModel):
    id: str
    user_id: str
    name: str
    media_type: str
    content_hash: str
    text: str = Field(exclude=True)
    size_bytes: int
    created_at: datetime


class DocumentPublic(StrictModel):
    id: str
    name: str
    media_type: str
    content_hash: str
    size_bytes: int
    created_at: datetime


class PlanStep(StrictModel):
    index: int = Field(ge=1, le=20)
    description: str = Field(min_length=1, max_length=500)


class MissionPlan(StrictModel):
    objective: str = Field(min_length=1, max_length=2_000)
    tool: Literal["conversation.answer", "document.report"]
    operation: Literal["answer", "generate"]
    resource: Literal[
        "urn:noosfera:tool:conversation-answer",
        "urn:noosfera:tool:document-report",
    ]
    steps: list[PlanStep] = Field(min_length=1, max_length=20)
    success_criteria: list[str] = Field(min_length=1, max_length=10)
    risk_factors: list[str] = Field(default_factory=list, max_length=10)
    requires_documents: bool


class EvidenceReference(StrictModel):
    document_id: str
    label: str


class ModelOutput(StrictModel):
    answer: str = Field(min_length=1, max_length=100_000)
    citations: list[EvidenceReference] = Field(default_factory=list, max_length=100)


class RiskDecision(StrictModel):
    risk_class: Literal["R0", "R1", "R2", "R3", "R4", "R5"]
    score: float = Field(ge=0, le=1)
    requires_approval: bool
    reasons: list[str] = Field(default_factory=list)


class Mission(StrictModel):
    id: str
    user_id: str
    conversation_id: str
    prompt: str
    document_ids: list[str]
    remember: bool
    status: MissionStatus
    plan: MissionPlan | None = None
    plan_hash: str | None = None
    risk: RiskDecision | None = None
    capability_id: str | None = None
    result: ModelOutput | None = None
    error: str | None = None
    version: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime


class MissionEvent(StrictModel):
    mission_id: str
    sequence: int = Field(ge=1)
    event_type: str
    payload: dict[str, Any]
    event_hash: str
    previous_receipt_hash: str
    receipt_hash: str
    created_at: datetime


class ApprovalRequest(StrictModel):
    approved: bool
    remember_result: bool | None = None
    reason: str = Field(default="", max_length=1_000)


class MemoryRecord(StrictModel):
    id: str
    user_id: str
    purpose: str
    content: str
    source_mission_id: str
    retention_days: int = Field(ge=1, le=3650)
    created_at: datetime
    deleted_at: datetime | None = None


class AuditEntry(StrictModel):
    mission_id: str
    sequence: int
    event_type: str
    event_hash: str
    previous_receipt_hash: str
    receipt_hash: str
    created_at: datetime


class OperatorStatus(StrictModel):
    stop_active: bool
    model_provider: str
    model_name: str
    storage_backend: str
    event_bus: str
    policy_engine: str
    execution_kernel: str


class StopRequest(StrictModel):
    active: bool
    reason: str = Field(min_length=1, max_length=500)
