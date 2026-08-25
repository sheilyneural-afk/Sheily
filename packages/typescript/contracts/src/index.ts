export type Urn = `urn:noosfera:${string}`;
export type Sha256 = string;

export type DataClassification =
  | "public"
  | "community"
  | "protected"
  | "intimate"
  | "cognitive"
  | "existential";

export type RiskClass = "R0" | "R1" | "R2" | "R3" | "R4" | "R5";

export interface Signature {
  signer: Urn;
  algorithm: string;
  value: string;
}

export interface IntentContract {
  id: Urn;
  requester: Urn;
  represented_parties: Urn[];
  objective: {
    desired_state: string;
    success_metrics: string[];
    forbidden_proxies: string[];
  };
  beneficiaries: Urn[];
  affected_parties: Urn[];
  scope: { spatial: string; temporal: string; systems: string[] };
  constraints: {
    rights: string[];
    prohibited_actions: string[];
    resource_limits: Record<string, { unit: string; maximum: number }>;
  };
  evidence_threshold: "low" | "medium" | "high" | "civilizational";
  reversibility_requirement: "none" | "preferred" | "required" | "staged" | "preserve-options";
  stop_conditions: string[];
  escalation_conditions: string[];
  authorization_basis: Urn[];
  expiry: string;
  ambiguity_register: string[];
  signatures: Signature[];
}

export interface Capability {
  id: Urn;
  issuer: Urn;
  holder: Urn;
  resource: Urn;
  permitted_operations: string[];
  plan_hash: Sha256;
  bounds: Record<string, { unit: string; maximum: number }>;
  preconditions: string[];
  mandatory_monitors: Urn[];
  stop_conditions: string[];
  not_before: string;
  expiry: string;
  max_uses: number;
  delegation: "forbidden" | "bounded";
  quorum_proof: Urn;
  revocation_channel: string;
  signature: Signature;
}

export interface MissionState {
  mission_id: Urn;
  intent_contract_id: Urn;
  state:
    | "received"
    | "clarification"
    | "compiled"
    | "analysis"
    | "deliberation"
    | "review"
    | "authorization"
    | "preparation"
    | "execution"
    | "paused"
    | "reversion"
    | "final-verification"
    | "closed"
    | "rejected"
    | "appeal";
  version: number;
  updated_at: string;
  last_event_id: Urn;
  active_capability_ids: Urn[];
}

export type AgentMissionStatus =
  | "received"
  | "planning"
  | "awaiting-approval"
  | "authorized"
  | "executing"
  | "verifying"
  | "completed"
  | "rejected"
  | "failed"
  | "stopped";

export interface AgentPlan {
  objective: string;
  tool: "conversation.answer" | "document.report";
  operation: "answer" | "generate";
  resource: string;
  steps: Array<{ index: number; description: string }>;
  success_criteria: string[];
  risk_factors: string[];
  requires_documents: boolean;
}

export interface AgentMission {
  id: string;
  user_id: string;
  conversation_id: string;
  prompt: string;
  document_ids: string[];
  remember: boolean;
  status: AgentMissionStatus;
  plan: AgentPlan | null;
  plan_hash: string | null;
  risk: {
    risk_class: RiskClass;
    score: number;
    requires_approval: boolean;
    reasons: string[];
  } | null;
  capability_id: string | null;
  result: {
    answer: string;
    citations: Array<{
      evidence_id: string;
      document_id: string;
      version_id: string;
      block_id: string;
      label: string;
      quote: string;
      page_number: number | null;
      section_path: string[];
      relation: "supports" | "contradicts" | "limits";
    }>;
    claims: Array<{
      id: string;
      statement: string;
      epistemic_status: "direct-observation" | "source-communication" | "inference" | "hypothesis";
      confidence: number;
      evidence_ids: string[];
    }>;
    contradictions: Array<{ id: string; statement: string; evidence_ids: string[] }>;
    limitations: Array<{
      id: string;
      statement: string;
      evidence_ids: string[];
      system_detected: boolean;
    }>;
    unknowns: string[];
    assumptions: string[];
    coverage: {
      total_blocks: number;
      analyzed_blocks: number;
      cited_blocks: number;
      critical_blocks: number;
      cited_critical_blocks: number;
      ratio: number;
      omitted_block_ids: string[];
    } | null;
    evidence_bundle: { mission_id: string } | null;
    verification_report: {
      status: "passed" | "passed-with-open-objections";
      verification_method: "structural-exact-quote-and-lexical-v1";
      evidence_bundle_hash: string;
      report_hash: string;
      verified_claim_ids: string[];
      rejected_claim_ids: string[];
      open_objections: string[];
      signed_at: string;
      key_id: string;
      algorithm: "Ed25519";
      signature: string;
    } | null;
    system_evidence: Array<{ source: string; evidence_hash: string; label: string }>;
    internal_state_claims: Array<{
      claim: string;
      observation_id: string | null;
      confidence: number;
      observed: boolean;
      sealed: boolean;
    }>;
  } | null;
  error: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface MissionEvent {
  mission_id: string;
  sequence: number;
  event_type: string;
  payload: Record<string, unknown>;
  receipt_hash: string;
  created_at: string;
}

export interface DocumentRecord {
  id: string;
  name: string;
  media_type: string;
  content_hash: string;
  normalized_hash: string;
  version_id: string;
  block_count: number;
  page_count: number | null;
  size_bytes: number;
  created_at: string;
}

export interface MemoryRecord {
  id: string;
  purpose: string;
  content: string;
  source_mission_id: string;
  retention_days: number;
  created_at: string;
}

export interface OperatorStatus {
  stop_active: boolean;
  model_provider: string;
  model_name: string;
  storage_backend: string;
  event_bus: string;
  policy_engine: string;
  execution_kernel: string;
}

export interface AuditEntry {
  mission_id: string;
  sequence: number;
  event_type: string;
  event_hash: string;
  receipt_hash: string;
  created_at: string;
}
