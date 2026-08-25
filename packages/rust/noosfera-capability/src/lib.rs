//! Tipos y validación temporal de capacidades Noosfera.

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use time::OffsetDateTime;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ResourceLimit {
    pub unit: String,
    pub maximum: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Capability {
    pub id: String,
    pub issuer: String,
    pub holder: String,
    pub mission_id: String,
    pub user_id: String,
    pub resource: String,
    pub permitted_operations: BTreeSet<String>,
    pub plan_hash: String,
    pub arguments_hash: String,
    pub bounds: BTreeMap<String, ResourceLimit>,
    pub preconditions: Vec<String>,
    pub mandatory_monitors: BTreeSet<String>,
    pub stop_conditions: Vec<String>,
    #[serde(with = "time::serde::rfc3339")]
    pub not_before: OffsetDateTime,
    #[serde(with = "time::serde::rfc3339")]
    pub expiry: OffsetDateTime,
    pub max_uses: u32,
    pub delegation: Delegation,
    pub network_allowed: bool,
    pub quorum_proof: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Delegation {
    Forbidden,
    Bounded,
}

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum CapabilityError {
    #[error("capability is not active yet")]
    NotActive,
    #[error("capability has expired")]
    Expired,
    #[error("capability is exhausted")]
    Exhausted,
    #[error("operation is not permitted")]
    OperationDenied,
    #[error("resource does not match")]
    ResourceMismatch,
    #[error("reference kernel forbids delegation")]
    DelegationDenied,
    #[error("a mandatory monitor is unavailable")]
    MonitorUnavailable,
    #[error("stop channel is unhealthy")]
    StopChannelUnavailable,
}

impl Capability {
    pub fn validate_use(
        &self,
        now: OffsetDateTime,
        operation: &str,
        resource: &str,
        healthy_monitors: &BTreeSet<String>,
        stop_channel_healthy: bool,
    ) -> Result<(), CapabilityError> {
        if now < self.not_before {
            return Err(CapabilityError::NotActive);
        }
        if now >= self.expiry {
            return Err(CapabilityError::Expired);
        }
        if self.max_uses == 0 {
            return Err(CapabilityError::Exhausted);
        }
        if !self.permitted_operations.contains(operation) {
            return Err(CapabilityError::OperationDenied);
        }
        if self.resource != resource {
            return Err(CapabilityError::ResourceMismatch);
        }
        if self.delegation != Delegation::Forbidden {
            return Err(CapabilityError::DelegationDenied);
        }
        if !self.mandatory_monitors.is_subset(healthy_monitors) {
            return Err(CapabilityError::MonitorUnavailable);
        }
        if !stop_channel_healthy {
            return Err(CapabilityError::StopChannelUnavailable);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use time::Duration;

    fn capability(now: OffsetDateTime) -> Capability {
        Capability {
            id: "urn:noosfera:capability:test".into(),
            issuer: "urn:noosfera:authority:test".into(),
            holder: "urn:noosfera:gateway:test".into(),
            mission_id: "urn:noosfera:mission:test".into(),
            user_id: "urn:noosfera:identity:test".into(),
            resource: "urn:noosfera:actuator:test".into(),
            permitted_operations: BTreeSet::from(["set".into()]),
            plan_hash: "00".repeat(32),
            arguments_hash: "11".repeat(32),
            bounds: BTreeMap::new(),
            preconditions: vec![],
            mandatory_monitors: BTreeSet::from(["monitor".into()]),
            stop_conditions: vec!["deviation".into()],
            not_before: now - Duration::minutes(1),
            expiry: now + Duration::minutes(1),
            max_uses: 1,
            delegation: Delegation::Forbidden,
            network_allowed: false,
            quorum_proof: "urn:noosfera:quorum:test".into(),
        }
    }

    #[test]
    fn accepts_bounded_use() {
        let now = OffsetDateTime::now_utc();
        assert_eq!(
            capability(now).validate_use(
                now,
                "set",
                "urn:noosfera:actuator:test",
                &BTreeSet::from(["monitor".into()]),
                true,
            ),
            Ok(())
        );
    }

    #[test]
    fn rejects_missing_stop_channel() {
        let now = OffsetDateTime::now_utc();
        assert_eq!(
            capability(now).validate_use(
                now,
                "set",
                "urn:noosfera:actuator:test",
                &BTreeSet::from(["monitor".into()]),
                false,
            ),
            Err(CapabilityError::StopChannelUnavailable)
        );
    }
}
