use noosfera_capability::{Capability, Delegation};
use noosfera_execution_kernel::{authorize_command, plan_hash, ExecutionError, ExecutionRequest};
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};
use time::{Duration, OffsetDateTime};

fn capability(hash: String, now: OffsetDateTime) -> Capability {
    Capability {
        id: "urn:noosfera:capability:test".into(),
        issuer: "urn:noosfera:authority:test".into(),
        holder: "urn:noosfera:gateway:test".into(),
        resource: "urn:noosfera:actuator:test".into(),
        permitted_operations: BTreeSet::from(["set".into()]),
        plan_hash: hash,
        bounds: BTreeMap::new(),
        preconditions: vec![],
        mandatory_monitors: BTreeSet::from(["monitor".into()]),
        stop_conditions: vec!["deviation".into()],
        not_before: now - Duration::minutes(1),
        expiry: now + Duration::minutes(1),
        max_uses: 1,
        delegation: Delegation::Forbidden,
        quorum_proof: "urn:noosfera:quorum:test".into(),
    }
}

#[test]
fn changed_plan_is_rejected() {
    let now = OffsetDateTime::now_utc();
    let original = json!({"operation": "set", "value": 1});
    let changed = json!({"operation": "set", "value": 2});
    let capability = capability(plan_hash(&original).unwrap(), now);
    let monitors = BTreeSet::from(["monitor".into()]);
    let result = authorize_command(ExecutionRequest {
        plan: &changed,
        capability: &capability,
        operation: "set",
        resource: "urn:noosfera:actuator:test",
        parameters: json!({"value": 2}),
        healthy_monitors: &monitors,
        stop_channel_healthy: true,
        now,
    });
    assert!(matches!(result, Err(ExecutionError::PlanHashMismatch)));
}
