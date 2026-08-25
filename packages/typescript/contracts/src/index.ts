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
