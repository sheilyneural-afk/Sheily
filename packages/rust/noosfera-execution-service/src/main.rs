//! Servicio de ejecución mínimo: valida una capacidad firmada y solo admite herramientas puras.

use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use hmac::{Hmac, Mac};
use noosfera_capability::Capability;
use noosfera_execution_kernel::{authorize_command, plan_hash, ExecutionRequest};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use sha2::Sha256;
use std::{
    collections::{BTreeSet, HashSet},
    env,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
};
use time::OffsetDateTime;

type HmacSha256 = Hmac<Sha256>;

#[derive(Clone)]
struct AppState {
    capability_secret: Arc<Vec<u8>>,
    stopped: Arc<AtomicBool>,
    used_capabilities: Arc<Mutex<HashSet<String>>>,
}

#[derive(Debug, Deserialize)]
struct ApiExecutionRequest {
    execution_id: String,
    plan: Value,
    plan_hash: String,
    capability: Value,
    capability_signature: String,
    tool: String,
    operation: String,
    resource: String,
    parameters: Value,
    healthy_monitors: BTreeSet<String>,
    stop_channel_healthy: bool,
}

#[derive(Debug, Serialize)]
struct ApiExecutionResponse {
    execution_id: String,
    status: &'static str,
    tool: String,
    output: Value,
    output_hash: String,
    kernel_receipt: String,
}

#[derive(Debug, Deserialize)]
struct StopRequest {
    active: bool,
    reason: String,
}

#[derive(Debug, Serialize)]
struct StopResponse {
    accepted: bool,
    active: bool,
}

#[derive(Debug, Serialize)]
struct ErrorResponse {
    error: String,
}

fn canonicalize(value: &Value) -> Value {
    match value {
        Value::Object(values) => {
            let mut keys: Vec<&String> = values.keys().collect();
            keys.sort();
            let mut result = Map::new();
            for key in keys {
                result.insert(key.clone(), canonicalize(&values[key]));
            }
            Value::Object(result)
        }
        Value::Array(values) => Value::Array(values.iter().map(canonicalize).collect()),
        _ => value.clone(),
    }
}

fn canonical_bytes(value: &Value) -> Result<Vec<u8>, String> {
    serde_json::to_vec(&canonicalize(value)).map_err(|error| error.to_string())
}

fn verify_signature(state: &AppState, capability: &Value, supplied: &str) -> Result<(), String> {
    let signature = hex::decode(supplied).map_err(|_| "invalid capability signature".to_owned())?;
    let mut verifier = HmacSha256::new_from_slice(state.capability_secret.as_ref())
        .map_err(|_| "invalid server capability secret".to_owned())?;
    verifier.update(&canonical_bytes(capability)?);
    verifier
        .verify_slice(&signature)
        .map_err(|_| "capability signature mismatch".to_owned())
}

fn validate_tool(request: &ApiExecutionRequest, maximum_output: usize) -> Result<(), String> {
    let expected = match request.tool.as_str() {
        "conversation.answer" => ("answer", "urn:noosfera:tool:conversation-answer", false),
        "document.report" => ("generate", "urn:noosfera:tool:document-report", true),
        _ => return Err("tool is not present in the Rust allowlist".to_owned()),
    };
    if request.operation != expected.0 || request.resource != expected.1 {
        return Err("tool operation or resource mismatch".to_owned());
    }
    let answer = request
        .parameters
        .get("answer")
        .and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| "tool output contains no answer".to_owned())?;
    if answer.len() > maximum_output {
        return Err("tool output exceeds capability bound".to_owned());
    }
    if expected.2 {
        let citations = request
            .parameters
            .get("citations")
            .and_then(Value::as_array)
            .ok_or_else(|| "document report contains no citations".to_owned())?;
        if citations.is_empty() {
            return Err("document report contains no citations".to_owned());
        }
    }
    Ok(())
}

async fn execute(
    State(state): State<AppState>,
    Json(request): Json<ApiExecutionRequest>,
) -> Result<Json<ApiExecutionResponse>, (StatusCode, Json<ErrorResponse>)> {
    let reject = |message: String| {
        (
            StatusCode::FORBIDDEN,
            Json(ErrorResponse { error: message }),
        )
    };
    if state.stopped.load(Ordering::SeqCst) || !request.stop_channel_healthy {
        return Err(reject("safe-stop channel is active".to_owned()));
    }
    verify_signature(&state, &request.capability, &request.capability_signature).map_err(reject)?;
    let capability: Capability = serde_json::from_value(request.capability.clone())
        .map_err(|error| reject(error.to_string()))?;
    if request.plan_hash != capability.plan_hash {
        return Err(reject(
            "declared plan hash does not match capability".to_owned(),
        ));
    }
    let actual_plan_hash = plan_hash(&request.plan).map_err(|error| reject(error.to_string()))?;
    if actual_plan_hash != request.plan_hash {
        return Err(reject("canonical plan hash mismatch".to_owned()));
    }
    let maximum_output = capability
        .bounds
        .get("output_bytes")
        .map(|limit| limit.maximum as usize)
        .ok_or_else(|| reject("capability has no output bound".to_owned()))?;
    validate_tool(&request, maximum_output).map_err(reject)?;
    authorize_command(ExecutionRequest {
        plan: &request.plan,
        capability: &capability,
        operation: &request.operation,
        resource: &request.resource,
        parameters: request.parameters.clone(),
        healthy_monitors: &request.healthy_monitors,
        stop_channel_healthy: request.stop_channel_healthy,
        now: OffsetDateTime::now_utc(),
    })
    .map_err(|error| reject(error.to_string()))?;
    let output_bytes = canonical_bytes(&request.parameters).map_err(reject)?;
    if output_bytes.len() > maximum_output {
        return Err(reject(
            "serialized tool output exceeds capability bound".to_owned(),
        ));
    }
    {
        let mut used = state
            .used_capabilities
            .lock()
            .map_err(|_| reject("capability ledger is unavailable".to_owned()))?;
        if !used.insert(capability.id.clone()) {
            return Err(reject("capability has already been consumed".to_owned()));
        }
    }
    let output_hash = noosfera_execution_kernel::sha256_hex(&output_bytes);
    let kernel_receipt = noosfera_execution_kernel::sha256_hex(
        format!(
            "{}|{}|{}|{}",
            request.execution_id, capability.id, request.plan_hash, output_hash
        )
        .as_bytes(),
    );
    Ok(Json(ApiExecutionResponse {
        execution_id: request.execution_id,
        status: "completed",
        tool: request.tool,
        output: request.parameters,
        output_hash,
        kernel_receipt,
    }))
}

async fn stop(
    State(state): State<AppState>,
    Json(request): Json<StopRequest>,
) -> Json<StopResponse> {
    let _reason_observed = !request.reason.trim().is_empty();
    state.stopped.store(request.active, Ordering::SeqCst);
    Json(StopResponse {
        accepted: true,
        active: request.active,
    })
}

async fn live() -> Json<Value> {
    Json(serde_json::json!({"status": "alive", "runtime": "rust"}))
}

async fn ready(State(state): State<AppState>) -> Json<Value> {
    Json(serde_json::json!({
        "status": "ready",
        "safe_stop": state.stopped.load(Ordering::SeqCst),
        "tools": ["conversation.answer", "document.report"]
    }))
}

#[tokio::main]
async fn main() {
    let secret = env::var("NOOSFERA_CAPABILITY_SECRET")
        .expect("NOOSFERA_CAPABILITY_SECRET is required for the Rust execution service");
    assert!(
        secret.len() >= 32,
        "capability secret must contain at least 32 characters"
    );
    let address = env::var("NOOSFERA_EXECUTION_BIND").unwrap_or_else(|_| "0.0.0.0:8080".to_owned());
    let state = AppState {
        capability_secret: Arc::new(secret.into_bytes()),
        stopped: Arc::new(AtomicBool::new(false)),
        used_capabilities: Arc::new(Mutex::new(HashSet::new())),
    };
    let app = Router::new()
        .route("/health/live", get(live))
        .route("/health/ready", get(ready))
        .route("/v1/executions", post(execute))
        .route("/v1/stop", post(stop))
        .with_state(state);
    let listener = tokio::net::TcpListener::bind(&address)
        .await
        .expect("execution service must bind its configured address");
    axum::serve(listener, app)
        .await
        .expect("execution service failed");
}

#[cfg(test)]
mod tests {
    use super::*;

    const TEST_SECRET: &[u8] = b"test-capability-secret-with-at-least-32-chars";

    fn state() -> AppState {
        AppState {
            capability_secret: Arc::new(TEST_SECRET.to_vec()),
            stopped: Arc::new(AtomicBool::new(false)),
            used_capabilities: Arc::new(Mutex::new(HashSet::new())),
        }
    }

    fn valid_request(capability_id: &str) -> ApiExecutionRequest {
        let plan = serde_json::json!({
            "objective": "Answer locally",
            "operation": "answer",
            "requires_documents": false,
            "resource": "urn:noosfera:tool:conversation-answer",
            "risk_factors": [],
            "steps": [{"description": "Answer", "index": 1}],
            "success_criteria": ["Non-empty"],
            "tool": "conversation.answer"
        });
        let active_plan_hash = plan_hash(&plan).unwrap();
        let now = OffsetDateTime::now_utc();
        let capability = serde_json::json!({
            "bounds": {
                "output_bytes": {"maximum": 2048, "unit": "bytes"},
                "wall_time": {"maximum": 30, "unit": "seconds"}
            },
            "delegation": "forbidden",
            "expiry": (now + time::Duration::minutes(1)).format(&time::format_description::well_known::Rfc3339).unwrap(),
            "holder": "urn:noosfera:service:experience",
            "id": capability_id,
            "issuer": "urn:noosfera:service:governance",
            "mandatory_monitors": [
                "urn:noosfera:monitor:model-local",
                "urn:noosfera:monitor:stop-channel"
            ],
            "max_uses": 1,
            "not_before": (now - time::Duration::seconds(1)).format(&time::format_description::well_known::Rfc3339).unwrap(),
            "permitted_operations": ["answer"],
            "plan_hash": active_plan_hash,
            "preconditions": ["owner-authorized"],
            "quorum_proof": "urn:noosfera:approval:test",
            "resource": "urn:noosfera:tool:conversation-answer",
            "stop_conditions": ["user-stop"]
        });
        let mut signer = HmacSha256::new_from_slice(TEST_SECRET).unwrap();
        signer.update(&canonical_bytes(&capability).unwrap());
        let signature = hex::encode(signer.finalize().into_bytes());
        ApiExecutionRequest {
            execution_id: uuid::Uuid::new_v4().to_string(),
            plan,
            plan_hash: active_plan_hash,
            capability,
            capability_signature: signature,
            tool: "conversation.answer".to_owned(),
            operation: "answer".to_owned(),
            resource: "urn:noosfera:tool:conversation-answer".to_owned(),
            parameters: serde_json::json!({"answer": "Verified", "citations": []}),
            healthy_monitors: BTreeSet::from([
                "urn:noosfera:monitor:model-local".to_owned(),
                "urn:noosfera:monitor:stop-channel".to_owned(),
            ]),
            stop_channel_healthy: true,
        }
    }

    #[test]
    fn canonical_json_sorts_object_keys() {
        let value = serde_json::json!({"z": 1, "a": {"d": 2, "b": 1}});
        assert_eq!(
            String::from_utf8(canonical_bytes(&value).unwrap()).unwrap(),
            r#"{"a":{"b":1,"d":2},"z":1}"#
        );
    }

    #[test]
    fn rejects_unknown_tool() {
        let request = ApiExecutionRequest {
            execution_id: uuid::Uuid::new_v4().to_string(),
            plan: serde_json::json!({}),
            plan_hash: "00".repeat(32),
            capability: serde_json::json!({}),
            capability_signature: "00".repeat(32),
            tool: "shell".to_owned(),
            operation: "run".to_owned(),
            resource: "host".to_owned(),
            parameters: serde_json::json!({"answer": "x"}),
            healthy_monitors: BTreeSet::new(),
            stop_channel_healthy: true,
        };
        assert!(validate_tool(&request, 100).is_err());
    }

    #[tokio::test]
    async fn accepts_a_valid_signed_capability_once() {
        let app_state = state();
        let capability_id = "urn:noosfera:capability:one-use";
        let response = execute(State(app_state.clone()), Json(valid_request(capability_id)))
            .await
            .unwrap();
        assert_eq!(response.0.status, "completed");

        let replay = execute(State(app_state), Json(valid_request(capability_id))).await;
        assert!(replay.is_err());
    }

    #[tokio::test]
    async fn rejects_a_tampered_signature() {
        let mut request = valid_request("urn:noosfera:capability:tampered");
        request.capability_signature = "00".repeat(32);
        let result = execute(State(state()), Json(request)).await;
        assert!(result.is_err());
    }
}
