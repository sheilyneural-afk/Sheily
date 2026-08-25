//! Núcleo mínimo que une un plan canónico y una capacidad antes de producir un comando.

use noosfera_capability::{Capability, CapabilityError};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use time::OffsetDateTime;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuthorizedCommand {
    pub capability_id: String,
    pub plan_hash: String,
    pub operation: String,
    pub resource: String,
    pub parameters: Value,
}

#[derive(Debug, thiserror::Error)]
pub enum ExecutionError {
    #[error("capability rejected: {0}")]
    Capability(#[from] CapabilityError),
    #[error("plan hash does not match capability")]
    PlanHashMismatch,
    #[error("plan cannot be serialized canonically")]
    InvalidPlan,
}

pub struct ExecutionRequest<'a> {
    pub plan: &'a Value,
    pub capability: &'a Capability,
    pub operation: &'a str,
    pub resource: &'a str,
    pub parameters: Value,
    pub healthy_monitors: &'a BTreeSet<String>,
    pub stop_channel_healthy: bool,
    pub now: OffsetDateTime,
}

pub fn plan_hash(plan: &Value) -> Result<String, ExecutionError> {
    let bytes = serde_json::to_vec(plan).map_err(|_| ExecutionError::InvalidPlan)?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}

pub fn authorize_command(
    request: ExecutionRequest<'_>,
) -> Result<AuthorizedCommand, ExecutionError> {
    request.capability.validate_use(
        request.now,
        request.operation,
        request.resource,
        request.healthy_monitors,
        request.stop_channel_healthy,
    )?;
    let actual_hash = plan_hash(request.plan)?;
    if actual_hash != request.capability.plan_hash {
        return Err(ExecutionError::PlanHashMismatch);
    }
    Ok(AuthorizedCommand {
        capability_id: request.capability.id.clone(),
        plan_hash: actual_hash,
        operation: request.operation.to_owned(),
        resource: request.resource.to_owned(),
        parameters: request.parameters,
    })
}
