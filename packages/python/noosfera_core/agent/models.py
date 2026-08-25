"""Modelos canónicos del agente funcional local-first."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class DocumentBlock(StrictModel):
    """Unidad direccionable conservada por la ingesta, no inventada por el modelo."""

    id: str
    document_id: str
    version_id: str
    ordinal: int = Field(ge=1)
    kind: Literal["heading", "paragraph", "list", "code", "table"]
    page_number: int | None = Field(default=None, ge=1)
    section_path: list[str] = Field(default_factory=list, max_length=20)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    text_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    text: str = Field(min_length=1, max_length=100_000)
    extraction_confidence: float = Field(default=1.0, ge=0, le=1)
    epistemic_status: Literal["communicated-source-content"] = "communicated-source-content"
    critical: bool = False


class DocumentRecord(StrictModel):
    id: str
    user_id: str
    name: str
    media_type: str
    content_hash: str
    normalized_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    version_id: str
    extractor: str = "noosfera-structural-ingest"
    extractor_version: str = "1.0.0"
    text: str = Field(exclude=True)
    blocks: list[DocumentBlock] = Field(default_factory=list)
    size_bytes: int
    created_at: datetime


class DocumentPublic(StrictModel):
    id: str
    name: str
    media_type: str
    content_hash: str
    normalized_hash: str
    version_id: str
    block_count: int = Field(ge=1)
    page_count: int | None = Field(default=None, ge=1)
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
    cognitive_cycle_id: str | None = None

    @model_validator(mode="after")
    def validate_tool_binding(self) -> Self:
        expected = {
            "conversation.answer": (
                "answer",
                "urn:noosfera:tool:conversation-answer",
                False,
            ),
            "document.report": (
                "generate",
                "urn:noosfera:tool:document-report",
                True,
            ),
        }[self.tool]
        actual = (self.operation, self.resource, self.requires_documents)
        if actual != expected:
            raise ValueError("tool, operation, resource and document scope are inconsistent")
        return self


class ResourceBudget(StrictModel):
    """Límites duros que viajan desde Agency hasta el núcleo Rust."""

    wall_time_seconds: int = Field(default=30, ge=1, le=300)
    cpu_time_ms: int = Field(default=5_000, ge=1, le=300_000)
    memory_bytes: int = Field(default=268_435_456, ge=1_048_576, le=4_294_967_296)
    input_bytes: int = Field(default=5_000_000, ge=1, le=100_000_000)
    output_bytes: int = Field(default=250_000, ge=1, le=10_000_000)
    model_input_tokens: int = Field(default=32_768, ge=1, le=1_000_000)
    model_output_tokens: int = Field(default=4_096, ge=1, le=100_000)
    cost_microunits: int = Field(default=0, ge=0, le=1_000_000_000)
    max_tool_calls: int = Field(default=1, ge=1, le=100)
    max_child_processes: int = Field(default=0, ge=0, le=16)
    network_allowed: bool = False


class PlanAttestation(StrictModel):
    """Plan causal validado y firmado exclusivamente por Agency."""

    mission_id: str
    user_id: str
    agent_id: str
    prompt_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    context_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    plan: MissionPlan
    plan_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    budget: ResourceBudget
    created_at: datetime
    expiry: datetime
    key_id: str
    algorithm: Literal["Ed25519"] = "Ed25519"
    signature: str


class ApprovalReceipt(StrictModel):
    """Consentimiento ligado a usuario, misión y plan; lo firma Identity."""

    id: str
    user_id: str
    mission_id: str
    plan_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    approved: bool
    remember_result: bool
    reason: str = Field(default="", max_length=1_000)
    issued_at: datetime
    expiry: datetime
    key_id: str
    algorithm: Literal["Ed25519"] = "Ed25519"
    signature: str


class CapabilityGrant(StrictModel):
    """Capacidad y firma separadas para evitar ambigüedad canónica."""

    capability: dict[str, Any]
    key_id: str
    algorithm: Literal["Ed25519"] = "Ed25519"
    signature: str


class StopDirective(StrictModel):
    """Orden monotónica de parada firmada por Governance."""

    id: str
    active: bool
    reason: str = Field(min_length=1, max_length=500)
    version: int = Field(ge=1)
    issued_by: str
    issued_at: datetime
    key_id: str
    algorithm: Literal["Ed25519"] = "Ed25519"
    signature: str


class RevocationDirective(StrictModel):
    id: str
    capability_id: str
    reason: str = Field(min_length=1, max_length=500)
    version: int = Field(ge=1)
    issued_by: str
    issued_at: datetime
    key_id: str
    algorithm: Literal["Ed25519"] = "Ed25519"
    signature: str


class Belief(StrictModel):
    proposition: str
    confidence: float = Field(ge=0, le=1)
    provenance: list[str] = Field(default_factory=list)


class DriveState(StrictModel):
    safety: float = Field(ge=0, le=1)
    privacy: float = Field(ge=0, le=1)
    epistemic_uncertainty: float = Field(ge=0, le=1)
    task_completion: float = Field(ge=0, le=1)
    resource_pressure: float = Field(ge=0, le=1)


class Goal(StrictModel):
    id: str
    description: str
    priority: float = Field(ge=0, le=1)
    source: Literal["user", "homeostasis", "constitutional"]


class CandidateAction(StrictModel):
    tool: Literal["conversation.answer", "document.report", "abstain"]
    utility: float = Field(ge=-1, le=1)
    risk: float = Field(ge=0, le=1)
    evidence_sufficiency: float = Field(ge=0, le=1)
    allowed: bool
    reasons: list[str]


class CognitiveCycle(StrictModel):
    id: str
    mission_id: str
    user_id: str
    observation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    drives: DriveState
    beliefs: list[Belief]
    goals: list[Goal]
    frontier: list[CandidateAction]
    selected_tool: Literal["conversation.answer", "document.report"]
    plan: MissionPlan
    uncertainty: float = Field(ge=0, le=1)
    explanation: list[str]
    created_at: datetime


class EvidenceReference(StrictModel):
    """Cita verificable a un fragmento exacto de una versión inmutable."""

    evidence_id: str
    document_id: str
    version_id: str
    block_id: str
    label: str
    quote: str = Field(min_length=1, max_length=10_000)
    page_number: int | None = Field(default=None, ge=1)
    section_path: list[str] = Field(default_factory=list, max_length=20)
    relation: Literal["supports", "contradicts", "limits"] = "supports"


class DocumentClaim(StrictModel):
    id: str
    statement: str = Field(min_length=1, max_length=5_000)
    epistemic_status: Literal[
        "direct-observation", "source-communication", "inference", "hypothesis"
    ]
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


class DocumentContradiction(StrictModel):
    id: str
    statement: str = Field(min_length=1, max_length=5_000)
    evidence_ids: list[str] = Field(min_length=2, max_length=20)


class DocumentLimitation(StrictModel):
    id: str
    statement: str = Field(min_length=1, max_length=5_000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    system_detected: bool = False


class CoverageReport(StrictModel):
    total_blocks: int = Field(ge=1)
    analyzed_blocks: int = Field(ge=1)
    cited_blocks: int = Field(ge=1)
    critical_blocks: int = Field(ge=0)
    cited_critical_blocks: int = Field(ge=0)
    ratio: float = Field(ge=0, le=1)
    omitted_block_ids: list[str] = Field(default_factory=list)


class DocumentSourceVersion(StrictModel):
    document_id: str
    version_id: str
    label: str
    media_type: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    normalized_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    extractor: str
    extractor_version: str
    total_blocks: int = Field(ge=1)


class DocumentEvidenceContext(StrictModel):
    source_versions: list[DocumentSourceVersion] = Field(min_length=1)
    blocks: list[DocumentBlock] = Field(min_length=1)
    total_block_ids: list[str] = Field(min_length=1)
    analyzed_block_ids: list[str] = Field(min_length=1)
    critical_block_ids: list[str] = Field(default_factory=list)
    missing_artifacts: list[str] = Field(default_factory=list)
    selection_method: Literal["critical-first-bm25-v1"] = "critical-first-bm25-v1"


class EvidenceBundle(StrictModel):
    mission_id: str
    source_versions: list[dict[str, Any]] = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(min_length=1)
    claims: list[DocumentClaim] = Field(min_length=1)
    transformations: list[str] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    counterevidence: list[DocumentContradiction] = Field(default_factory=list)
    open_objections: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    coverage: CoverageReport


class DocumentVerificationReport(StrictModel):
    status: Literal["passed", "passed-with-open-objections"]
    verification_method: Literal["structural-exact-quote-and-lexical-v1"]
    evidence_bundle_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    verified_claim_ids: list[str]
    rejected_claim_ids: list[str] = Field(default_factory=list)
    open_objections: list[str] = Field(default_factory=list)
    signed_at: datetime
    key_id: str
    algorithm: Literal["Ed25519"] = "Ed25519"
    signature: str


class ModelDraft(StrictModel):
    """Borrador del LLM. No contiene sellos ni estados de verificación."""

    answer: str = Field(min_length=1, max_length=100_000)
    citations: list[EvidenceReference] = Field(default_factory=list, max_length=100)
    claims: list[DocumentClaim] = Field(default_factory=list, max_length=100)
    contradictions: list[DocumentContradiction] = Field(default_factory=list, max_length=50)
    limitations: list[DocumentLimitation] = Field(default_factory=list, max_length=50)
    unknowns: list[str] = Field(default_factory=list, max_length=50)
    assumptions: list[str] = Field(default_factory=list, max_length=50)


class DocumentVerificationInput(StrictModel):
    mission_id: str
    prompt: str = Field(min_length=1, max_length=20_000)
    context: DocumentEvidenceContext
    draft: ModelDraft


class SystemEvidenceReference(StrictModel):
    """Referencia a evidencia producida por un subsistema verificable de Sheily."""

    source: str
    evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    label: str


class InternalStateClaim(StrictModel):
    claim: str = Field(min_length=1, max_length=500)
    observation_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    observed: bool
    sealed: bool


class ModelOutput(StrictModel):
    answer: str = Field(min_length=1, max_length=100_000)
    citations: list[EvidenceReference] = Field(default_factory=list, max_length=100)
    claims: list[DocumentClaim] = Field(default_factory=list, max_length=100)
    contradictions: list[DocumentContradiction] = Field(default_factory=list, max_length=50)
    limitations: list[DocumentLimitation] = Field(default_factory=list, max_length=50)
    unknowns: list[str] = Field(default_factory=list, max_length=50)
    assumptions: list[str] = Field(default_factory=list, max_length=50)
    coverage: CoverageReport | None = None
    evidence_bundle: EvidenceBundle | None = None
    verification_report: DocumentVerificationReport | None = None
    system_evidence: list[SystemEvidenceReference] = Field(default_factory=list, max_length=20)
    internal_state_claims: list[InternalStateClaim] = Field(default_factory=list, max_length=20)


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
    plan_attestation: PlanAttestation | None = None
    cognitive_cycle_id: str | None = None
    risk: RiskDecision | None = None
    approval_receipt: ApprovalReceipt | None = None
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


class AuditAnchor(StrictModel):
    id: str
    first_event: str
    last_event: str
    event_count: int = Field(ge=1)
    merkle_root: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    key_id: str
    algorithm: Literal["Ed25519"] = "Ed25519"
    signature: str


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


class RevocationRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=500)
