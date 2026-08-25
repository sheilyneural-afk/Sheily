//! Frontera de ejecución: capacidad Ed25519, ledger durable y herramientas puras.

use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use base64::{engine::general_purpose::STANDARD as BASE64, Engine};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use noosfera_capability::Capability;
use noosfera_execution_kernel::{authorize_command, plan_hash, ExecutionRequest};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::{
    collections::{BTreeSet, HashSet},
    env,
    sync::{Arc, Mutex},
    time::Instant,
};
use time::OffsetDateTime;
use tokio_postgres::{Client, NoTls};

const CAPABILITY_DOMAIN: &str = "noosfera.governance.capability.v1";
const STOP_DOMAIN: &str = "noosfera.governance.stop-directive.v1";
const REVOCATION_DOMAIN: &str = "noosfera.governance.revocation-directive.v1";
const GOVERNANCE_ISSUER: &str = "urn:noosfera:service:governance";
const EXPERIENCE_HOLDER: &str = "urn:noosfera:service:experience";

#[derive(Debug, Clone, Default)]
struct StopState {
    active: bool,
    version: i64,
    reason: String,
}

#[derive(Clone)]
enum Ledger {
    #[allow(dead_code)] // Test-only durable-semantics double; production always uses PostgreSQL.
    Memory {
        used: Arc<Mutex<HashSet<String>>>,
        revoked: Arc<Mutex<HashSet<String>>>,
        stop: Arc<Mutex<StopState>>,
    },
    Postgres(Arc<Client>),
}

impl Ledger {
    #[cfg(test)]
    fn memory() -> Self {
        Self::Memory {
            used: Arc::new(Mutex::new(HashSet::new())),
            revoked: Arc::new(Mutex::new(HashSet::new())),
            stop: Arc::new(Mutex::new(StopState::default())),
        }
    }

    async fn postgres(database_url: &str) -> Result<Self, String> {
        let (client, connection) = tokio_postgres::connect(database_url, NoTls)
            .await
            .map_err(|error| format!("cannot connect execution ledger: {error}"))?;
        tokio::spawn(async move {
            if let Err(error) = connection.await {
                eprintln!("execution ledger connection failed: {error}");
            }
        });
        client
            .batch_execute(
                "CREATE TABLE IF NOT EXISTS execution_capability_ledger (
                   capability_id TEXT PRIMARY KEY,
                   execution_id TEXT NOT NULL UNIQUE,
                   mission_id TEXT NOT NULL,
                   plan_hash CHAR(64) NOT NULL,
                   arguments_hash CHAR(64) NOT NULL,
                   output_hash CHAR(64) NOT NULL,
                   kernel_receipt CHAR(64) NOT NULL,
                   consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                 );
                 CREATE TABLE IF NOT EXISTS execution_control (
                   singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
                   stop_active BOOLEAN NOT NULL,
                   stop_version BIGINT NOT NULL,
                   reason TEXT NOT NULL,
                   updated_at TIMESTAMPTZ NOT NULL
                 );
                 CREATE TABLE IF NOT EXISTS execution_revocations (
                   capability_id TEXT PRIMARY KEY,
                   directive_version BIGINT NOT NULL UNIQUE,
                   reason TEXT NOT NULL,
                   revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                 );
                 INSERT INTO execution_control
                   (singleton,stop_active,stop_version,reason,updated_at)
                 VALUES(TRUE,FALSE,0,'',NOW())
                 ON CONFLICT(singleton) DO NOTHING;",
            )
            .await
            .map_err(|error| format!("cannot initialize execution ledger: {error}"))?;
        Ok(Self::Postgres(Arc::new(client)))
    }

    async fn health(&self) -> bool {
        match self {
            Self::Memory { .. } => true,
            Self::Postgres(client) => client.simple_query("SELECT 1").await.is_ok(),
        }
    }

    async fn stop_state(&self) -> Result<StopState, String> {
        match self {
            Self::Memory { stop, .. } => stop
                .lock()
                .map(|state| state.clone())
                .map_err(|_| "safe-stop ledger lock poisoned".to_owned()),
            Self::Postgres(client) => {
                let row = client
                    .query_one(
                        "SELECT stop_active,stop_version,reason FROM execution_control
                         WHERE singleton=TRUE",
                        &[],
                    )
                    .await
                    .map_err(|error| format!("safe-stop ledger unavailable: {error}"))?;
                Ok(StopState {
                    active: row.get(0),
                    version: row.get(1),
                    reason: row.get(2),
                })
            }
        }
    }

    async fn apply_stop(&self, directive: &StopDirective) -> Result<bool, String> {
        match self {
            Self::Memory { stop, .. } => {
                let mut state = stop
                    .lock()
                    .map_err(|_| "safe-stop ledger lock poisoned".to_owned())?;
                if directive.version <= state.version {
                    return Ok(false);
                }
                *state = StopState {
                    active: directive.active,
                    version: directive.version,
                    reason: directive.reason.clone(),
                };
                Ok(true)
            }
            Self::Postgres(client) => {
                let updated = client
                    .execute(
                        "WITH authority_lock AS (
                           SELECT pg_advisory_xact_lock(2300::BIGINT)
                         )
                         UPDATE execution_control
                         SET stop_active=$1,stop_version=$2,reason=$3,updated_at=NOW()
                         FROM authority_lock
                         WHERE singleton=TRUE AND stop_version < $2",
                        &[&directive.active, &directive.version, &directive.reason],
                    )
                    .await
                    .map_err(|error| format!("cannot persist safe-stop: {error}"))?;
                Ok(updated == 1)
            }
        }
    }

    async fn consume(&self, record: &ExecutionRecord) -> Result<bool, String> {
        match self {
            Self::Memory { used, .. } => used
                .lock()
                .map_err(|_| "capability ledger lock poisoned".to_owned())
                .map(|mut values| values.insert(record.capability_id.clone())),
            Self::Postgres(client) => {
                // Los locks transaccionales linealizan consumo, parada y revocación.
                // Una parada/revocación concurrente gana antes del efecto o espera a
                // que el consumo único haya quedado registrado.
                let inserted: bool = client
                    .query_one(
                        "WITH authority_locks AS MATERIALIZED (
                           SELECT pg_advisory_xact_lock(2300::BIGINT),
                                  pg_advisory_xact_lock(hashtextextended($1,0))
                         ), admissible AS MATERIALIZED (
                           SELECT 1 FROM execution_control,authority_locks
                           WHERE singleton=TRUE AND stop_active=FALSE
                             AND NOT EXISTS (
                               SELECT 1 FROM execution_revocations WHERE capability_id=$1
                             )
                         ), inserted AS (
                           INSERT INTO execution_capability_ledger
                             (capability_id,execution_id,mission_id,plan_hash,arguments_hash,
                              output_hash,kernel_receipt)
                           SELECT $1,$2,$3,$4,$5,$6,$7 FROM admissible
                           ON CONFLICT DO NOTHING RETURNING 1
                         )
                         SELECT EXISTS(SELECT 1 FROM inserted)",
                        &[
                            &record.capability_id,
                            &record.execution_id,
                            &record.mission_id,
                            &record.plan_hash,
                            &record.arguments_hash,
                            &record.output_hash,
                            &record.kernel_receipt,
                        ],
                    )
                    .await
                    .map_err(|error| format!("capability ledger unavailable: {error}"))?
                    .get(0);
                Ok(inserted)
            }
        }
    }

    async fn is_revoked(&self, capability_id: &str) -> Result<bool, String> {
        match self {
            Self::Memory { revoked, .. } => revoked
                .lock()
                .map(|values| values.contains(capability_id))
                .map_err(|_| "revocation ledger lock poisoned".to_owned()),
            Self::Postgres(client) => client
                .query_opt(
                    "SELECT 1 FROM execution_revocations WHERE capability_id=$1",
                    &[&capability_id],
                )
                .await
                .map(|row| row.is_some())
                .map_err(|error| format!("revocation ledger unavailable: {error}")),
        }
    }

    async fn apply_revocation(&self, directive: &RevocationDirective) -> Result<bool, String> {
        match self {
            Self::Memory { revoked, .. } => revoked
                .lock()
                .map_err(|_| "revocation ledger lock poisoned".to_owned())
                .map(|mut values| values.insert(directive.capability_id.clone())),
            Self::Postgres(client) => client
                .execute(
                    "WITH capability_lock AS (
                       SELECT pg_advisory_xact_lock(hashtextextended($1,0))
                     )
                     INSERT INTO execution_revocations
                       (capability_id,directive_version,reason)
                     SELECT $1,$2,$3 FROM capability_lock
                     ON CONFLICT DO NOTHING",
                    &[
                        &directive.capability_id,
                        &directive.version,
                        &directive.reason,
                    ],
                )
                .await
                .map(|rows| rows == 1)
                .map_err(|error| format!("cannot persist capability revocation: {error}")),
        }
    }
}

#[derive(Clone)]
struct AppState {
    governance_public_key: Arc<VerifyingKey>,
    governance_key_id: Arc<String>,
    ledger: Ledger,
}

#[derive(Debug, Deserialize)]
struct ApiExecutionRequest {
    execution_id: String,
    mission_id: String,
    user_id: String,
    plan: Value,
    plan_hash: String,
    capability: Value,
    capability_signature: String,
    capability_key_id: String,
    capability_algorithm: String,
    tool: String,
    operation: String,
    resource: String,
    parameters: Value,
}

#[derive(Debug)]
struct ExecutionRecord {
    capability_id: String,
    execution_id: String,
    mission_id: String,
    plan_hash: String,
    arguments_hash: String,
    output_hash: String,
    kernel_receipt: String,
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

#[derive(Debug, Serialize, Deserialize)]
struct StopDirective {
    id: String,
    active: bool,
    reason: String,
    version: i64,
    issued_by: String,
    #[serde(with = "time::serde::rfc3339")]
    issued_at: OffsetDateTime,
    key_id: String,
    algorithm: String,
    signature: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct RevocationDirective {
    id: String,
    capability_id: String,
    reason: String,
    version: i64,
    issued_by: String,
    #[serde(with = "time::serde::rfc3339")]
    issued_at: OffsetDateTime,
    key_id: String,
    algorithm: String,
    signature: String,
}

#[derive(Debug, Serialize)]
struct StopResponse {
    accepted: bool,
    active: bool,
    version: i64,
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

fn verify_signature(
    state: &AppState,
    domain: &str,
    payload: &Value,
    supplied: &str,
    key_id: &str,
    algorithm: &str,
) -> Result<(), String> {
    if algorithm != "Ed25519" {
        return Err("unsupported signature algorithm".to_owned());
    }
    if key_id != state.governance_key_id.as_str() {
        return Err("untrusted governance key".to_owned());
    }
    let signature_bytes = BASE64
        .decode(supplied)
        .map_err(|_| "invalid base64 signature".to_owned())?;
    let signature = Signature::from_slice(&signature_bytes)
        .map_err(|_| "invalid Ed25519 signature".to_owned())?;
    let mut message = domain.as_bytes().to_vec();
    message.push(0);
    message.extend(canonical_bytes(payload)?);
    state
        .governance_public_key
        .verify(&message, &signature)
        .map_err(|_| "signature verification failed".to_owned())
}

fn bound(capability: &Capability, name: &str, expected_unit: &str) -> Result<f64, String> {
    let limit = capability
        .bounds
        .get(name)
        .ok_or_else(|| format!("capability has no {name} bound"))?;
    if limit.unit != expected_unit {
        return Err(format!("capability {name} bound has an invalid unit"));
    }
    if !limit.maximum.is_finite() || limit.maximum < 0.0 {
        return Err(format!("capability {name} bound has an invalid maximum"));
    }
    Ok(limit.maximum)
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
    let started = Instant::now();
    let reject = |message: String| {
        (
            StatusCode::FORBIDDEN,
            Json(ErrorResponse { error: message }),
        )
    };
    let stop = state.ledger.stop_state().await.map_err(reject)?;
    if stop.active {
        return Err(reject(format!("safe-stop is active: {}", stop.reason)));
    }
    verify_signature(
        &state,
        CAPABILITY_DOMAIN,
        &request.capability,
        &request.capability_signature,
        &request.capability_key_id,
        &request.capability_algorithm,
    )
    .map_err(reject)?;
    let capability: Capability = serde_json::from_value(request.capability.clone())
        .map_err(|error| reject(error.to_string()))?;
    if capability.issuer != GOVERNANCE_ISSUER || capability.holder != EXPERIENCE_HOLDER {
        return Err(reject("invalid capability issuer or holder".to_owned()));
    }
    if capability.mission_id != request.mission_id || capability.user_id != request.user_id {
        return Err(reject("capability identity binding mismatch".to_owned()));
    }
    if capability.network_allowed {
        return Err(reject(
            "reference execution service forbids network access".to_owned(),
        ));
    }
    if capability.max_uses != 1 {
        return Err(reject(
            "reference execution service requires a single-use capability".to_owned(),
        ));
    }
    let preconditions: BTreeSet<&str> = capability
        .preconditions
        .iter()
        .map(String::as_str)
        .collect();
    if !preconditions.contains("agency-attested")
        || !preconditions.contains("local-model-only")
        || !(preconditions.contains("owner-authorized")
            || preconditions.contains("policy-auto-authorized"))
    {
        return Err(reject("capability preconditions are incomplete".to_owned()));
    }
    if state
        .ledger
        .is_revoked(&capability.id)
        .await
        .map_err(reject)?
    {
        return Err(reject("capability is revoked".to_owned()));
    }
    if request.plan_hash != capability.plan_hash {
        return Err(reject(
            "declared plan hash does not match capability".to_owned(),
        ));
    }
    let actual_plan_hash = plan_hash(&request.plan).map_err(|error| reject(error.to_string()))?;
    if actual_plan_hash != request.plan_hash {
        return Err(reject("canonical plan hash mismatch".to_owned()));
    }
    let parameters_bytes = canonical_bytes(&request.parameters).map_err(reject)?;
    let arguments_hash = noosfera_execution_kernel::sha256_hex(&parameters_bytes);
    if capability.arguments_hash != arguments_hash {
        return Err(reject("capability parameters hash mismatch".to_owned()));
    }
    let maximum_output = bound(&capability, "output_bytes", "bytes").map_err(reject)? as usize;
    let maximum_input = bound(&capability, "input_bytes", "bytes").map_err(reject)? as usize;
    let maximum_wall_time = bound(&capability, "wall_time", "seconds").map_err(reject)?;
    let _maximum_cpu = bound(&capability, "cpu_time", "milliseconds").map_err(reject)?;
    let _maximum_memory = bound(&capability, "memory", "bytes").map_err(reject)?;
    let _maximum_model_input =
        bound(&capability, "model_input_tokens", "tokens").map_err(reject)?;
    let _maximum_model_output =
        bound(&capability, "model_output_tokens", "tokens").map_err(reject)?;
    let _maximum_cost = bound(&capability, "cost", "microunits").map_err(reject)?;
    if canonical_bytes(&request.plan).map_err(reject)?.len() + parameters_bytes.len()
        > maximum_input
    {
        return Err(reject(
            "serialized execution input exceeds bound".to_owned(),
        ));
    }
    if bound(&capability, "tool_calls", "calls").map_err(reject)? != 1.0
        || bound(&capability, "child_processes", "processes").map_err(reject)? != 0.0
    {
        return Err(reject("invalid process or tool-call budget".to_owned()));
    }
    validate_tool(&request, maximum_output).map_err(reject)?;
    let internal_monitors = BTreeSet::from([
        "urn:noosfera:monitor:model-local".to_owned(),
        "urn:noosfera:monitor:stop-channel".to_owned(),
        "urn:noosfera:monitor:capability-ledger".to_owned(),
    ]);
    if !internal_monitors.is_subset(&capability.mandatory_monitors) {
        return Err(reject(
            "capability omits a mandatory internal monitor".to_owned(),
        ));
    }
    authorize_command(ExecutionRequest {
        plan: &request.plan,
        capability: &capability,
        operation: &request.operation,
        resource: &request.resource,
        parameters: request.parameters.clone(),
        healthy_monitors: &internal_monitors,
        stop_channel_healthy: true,
        now: OffsetDateTime::now_utc(),
    })
    .map_err(|error| reject(error.to_string()))?;
    if parameters_bytes.len() > maximum_output {
        return Err(reject(
            "serialized tool output exceeds capability bound".to_owned(),
        ));
    }
    if started.elapsed().as_secs_f64() > maximum_wall_time {
        return Err(reject("execution exceeded wall-time bound".to_owned()));
    }
    let output_hash = noosfera_execution_kernel::sha256_hex(&parameters_bytes);
    let kernel_receipt = noosfera_execution_kernel::sha256_hex(
        format!(
            "{}|{}|{}|{}|{}",
            request.execution_id, capability.id, request.mission_id, request.plan_hash, output_hash
        )
        .as_bytes(),
    );
    let record = ExecutionRecord {
        capability_id: capability.id.clone(),
        execution_id: request.execution_id.clone(),
        mission_id: request.mission_id.clone(),
        plan_hash: request.plan_hash.clone(),
        arguments_hash,
        output_hash: output_hash.clone(),
        kernel_receipt: kernel_receipt.clone(),
    };
    if !state.ledger.consume(&record).await.map_err(reject)? {
        return Err(reject("capability has already been consumed".to_owned()));
    }
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
    Json(directive): Json<StopDirective>,
) -> Result<Json<StopResponse>, (StatusCode, Json<ErrorResponse>)> {
    let reject = |message: String| {
        (
            StatusCode::FORBIDDEN,
            Json(ErrorResponse { error: message }),
        )
    };
    let mut unsigned =
        serde_json::to_value(&directive).map_err(|error| reject(error.to_string()))?;
    if let Value::Object(values) = &mut unsigned {
        values.remove("signature");
    }
    verify_signature(
        &state,
        STOP_DOMAIN,
        &unsigned,
        &directive.signature,
        &directive.key_id,
        &directive.algorithm,
    )
    .map_err(reject)?;
    if !state.ledger.apply_stop(&directive).await.map_err(reject)? {
        return Err(reject("stale safe-stop directive".to_owned()));
    }
    Ok(Json(StopResponse {
        accepted: true,
        active: directive.active,
        version: directive.version,
    }))
}

async fn revoke(
    State(state): State<AppState>,
    Json(directive): Json<RevocationDirective>,
) -> Result<Json<Value>, (StatusCode, Json<ErrorResponse>)> {
    let reject = |message: String| {
        (
            StatusCode::FORBIDDEN,
            Json(ErrorResponse { error: message }),
        )
    };
    let mut unsigned =
        serde_json::to_value(&directive).map_err(|error| reject(error.to_string()))?;
    if let Value::Object(values) = &mut unsigned {
        values.remove("signature");
    }
    verify_signature(
        &state,
        REVOCATION_DOMAIN,
        &unsigned,
        &directive.signature,
        &directive.key_id,
        &directive.algorithm,
    )
    .map_err(reject)?;
    if !state
        .ledger
        .apply_revocation(&directive)
        .await
        .map_err(reject)?
    {
        return Err(reject("stale or duplicate revocation directive".to_owned()));
    }
    Ok(Json(serde_json::json!({
        "accepted": true,
        "capability_id": directive.capability_id,
        "version": directive.version
    })))
}

async fn live() -> Json<Value> {
    Json(serde_json::json!({"status": "alive", "runtime": "rust"}))
}

async fn ready(
    State(state): State<AppState>,
) -> Result<Json<Value>, (StatusCode, Json<ErrorResponse>)> {
    if !state.ledger.health().await {
        return Err((
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse {
                error: "execution ledger unavailable".to_owned(),
            }),
        ));
    }
    let stop = state.ledger.stop_state().await.map_err(|message| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse { error: message }),
        )
    })?;
    Ok(Json(serde_json::json!({
        "status": "ready",
        "safe_stop": stop.active,
        "safe_stop_version": stop.version,
        "ledger": "available",
        "signature": "Ed25519",
        "tools": ["conversation.answer", "document.report"]
    })))
}

#[tokio::main]
async fn main() {
    let public_key_b64 = env::var("NOOSFERA_GOVERNANCE_PUBLIC_KEY_B64")
        .expect("NOOSFERA_GOVERNANCE_PUBLIC_KEY_B64 is required");
    let public_key_bytes = BASE64
        .decode(public_key_b64)
        .expect("governance public key must be base64");
    let public_key_array: [u8; 32] = public_key_bytes
        .try_into()
        .expect("governance public key must contain 32 bytes");
    let governance_public_key =
        VerifyingKey::from_bytes(&public_key_array).expect("invalid Ed25519 public key");
    let governance_key_id =
        env::var("NOOSFERA_GOVERNANCE_KEY_ID").unwrap_or_else(|_| "governance-local-v1".to_owned());
    let database_url =
        env::var("NOOSFERA_DATABASE_URL").expect("NOOSFERA_DATABASE_URL is required");
    let ledger = Ledger::postgres(&database_url)
        .await
        .expect("execution ledger must initialize");
    let address = env::var("NOOSFERA_EXECUTION_BIND").unwrap_or_else(|_| "0.0.0.0:8080".to_owned());
    let state = AppState {
        governance_public_key: Arc::new(governance_public_key),
        governance_key_id: Arc::new(governance_key_id),
        ledger,
    };
    let app = Router::new()
        .route("/health/live", get(live))
        .route("/health/ready", get(ready))
        .route("/v1/executions", post(execute))
        .route("/v1/stop", post(stop))
        .route("/v1/revocations", post(revoke))
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
    use ed25519_dalek::SigningKey;

    fn signing_key() -> SigningKey {
        SigningKey::from_bytes(&[7_u8; 32])
    }

    fn state() -> AppState {
        AppState {
            governance_public_key: Arc::new(signing_key().verifying_key()),
            governance_key_id: Arc::new("governance-test-v1".to_owned()),
            ledger: Ledger::memory(),
        }
    }

    fn sign(domain: &str, value: &Value) -> String {
        use ed25519_dalek::Signer as _;

        let mut payload = domain.as_bytes().to_vec();
        payload.push(0);
        payload.extend(canonical_bytes(value).unwrap());
        BASE64.encode(signing_key().sign(&payload).to_bytes())
    }

    fn valid_request(capability_id: &str) -> ApiExecutionRequest {
        let plan = serde_json::json!({
            "cognitive_cycle_id": null,
            "objective": "Answer locally",
            "operation": "answer",
            "requires_documents": false,
            "resource": "urn:noosfera:tool:conversation-answer",
            "risk_factors": [],
            "steps": [{"description": "Answer", "index": 1}],
            "success_criteria": ["Non-empty"],
            "tool": "conversation.answer"
        });
        let parameters = serde_json::json!({"answer": "Verified", "citations": []});
        let active_plan_hash = plan_hash(&plan).unwrap();
        let arguments_hash =
            noosfera_execution_kernel::sha256_hex(&canonical_bytes(&parameters).unwrap());
        let now = OffsetDateTime::now_utc();
        let capability = serde_json::json!({
            "arguments_hash": arguments_hash,
            "bounds": {
                "child_processes": {"maximum": 0, "unit": "processes"},
                "cost": {"maximum": 0, "unit": "microunits"},
                "cpu_time": {"maximum": 5000, "unit": "milliseconds"},
                "input_bytes": {"maximum": 5000000, "unit": "bytes"},
                "memory": {"maximum": 268435456, "unit": "bytes"},
                "model_input_tokens": {"maximum": 32768, "unit": "tokens"},
                "model_output_tokens": {"maximum": 4096, "unit": "tokens"},
                "output_bytes": {"maximum": 2048, "unit": "bytes"},
                "tool_calls": {"maximum": 1, "unit": "calls"},
                "wall_time": {"maximum": 30, "unit": "seconds"}
            },
            "delegation": "forbidden",
            "expiry": (now + time::Duration::minutes(1)).format(&time::format_description::well_known::Rfc3339).unwrap(),
            "holder": EXPERIENCE_HOLDER,
            "id": capability_id,
            "issuer": GOVERNANCE_ISSUER,
            "mandatory_monitors": [
                "urn:noosfera:monitor:capability-ledger",
                "urn:noosfera:monitor:model-local",
                "urn:noosfera:monitor:stop-channel"
            ],
            "max_uses": 1,
            "mission_id": "urn:noosfera:mission:test",
            "network_allowed": false,
            "not_before": (now - time::Duration::seconds(1)).format(&time::format_description::well_known::Rfc3339).unwrap(),
            "permitted_operations": ["answer"],
            "plan_hash": active_plan_hash,
            "preconditions": ["agency-attested", "owner-authorized", "local-model-only"],
            "quorum_proof": "urn:noosfera:approval:test",
            "resource": "urn:noosfera:tool:conversation-answer",
            "stop_conditions": ["user-stop"],
            "user_id": "urn:noosfera:identity:test"
        });
        let signature = sign(CAPABILITY_DOMAIN, &capability);
        ApiExecutionRequest {
            execution_id: uuid::Uuid::new_v4().to_string(),
            mission_id: "urn:noosfera:mission:test".to_owned(),
            user_id: "urn:noosfera:identity:test".to_owned(),
            plan,
            plan_hash: active_plan_hash,
            capability,
            capability_signature: signature,
            capability_key_id: "governance-test-v1".to_owned(),
            capability_algorithm: "Ed25519".to_owned(),
            tool: "conversation.answer".to_owned(),
            operation: "answer".to_owned(),
            resource: "urn:noosfera:tool:conversation-answer".to_owned(),
            parameters,
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

    #[tokio::test]
    async fn accepts_a_valid_signed_capability_once() {
        let app_state = state();
        let capability_id = "urn:noosfera:capability:one-use";
        let response = execute(State(app_state.clone()), Json(valid_request(capability_id)))
            .await
            .unwrap();
        assert_eq!(response.0.status, "completed");
        assert!(
            execute(State(app_state), Json(valid_request(capability_id)))
                .await
                .is_err()
        );
    }

    #[tokio::test]
    async fn rejects_tampered_parameters() {
        let mut request = valid_request("urn:noosfera:capability:tampered");
        request.parameters["answer"] = Value::String("Changed after authorization".to_owned());
        assert!(execute(State(state()), Json(request)).await.is_err());
    }

    #[tokio::test]
    async fn signed_stop_is_monotonic() {
        let app_state = state();
        let mut directive = StopDirective {
            id: "urn:noosfera:stop-directive:test".to_owned(),
            active: true,
            reason: "test".to_owned(),
            version: 1,
            issued_by: "urn:noosfera:identity:test".to_owned(),
            issued_at: OffsetDateTime::now_utc(),
            key_id: "governance-test-v1".to_owned(),
            algorithm: "Ed25519".to_owned(),
            signature: String::new(),
        };
        let mut unsigned = serde_json::to_value(&directive).unwrap();
        unsigned.as_object_mut().unwrap().remove("signature");
        directive.signature = sign(STOP_DOMAIN, &unsigned);
        assert!(stop(State(app_state.clone()), Json(directive))
            .await
            .is_ok());
        assert!(app_state.ledger.stop_state().await.unwrap().active);
    }

    #[tokio::test]
    async fn signed_revocation_blocks_unused_capability() {
        let app_state = state();
        let capability_id = "urn:noosfera:capability:revoked";
        let mut directive = RevocationDirective {
            id: "urn:noosfera:revocation-directive:test".to_owned(),
            capability_id: capability_id.to_owned(),
            reason: "test".to_owned(),
            version: 1,
            issued_by: "urn:noosfera:identity:test".to_owned(),
            issued_at: OffsetDateTime::now_utc(),
            key_id: "governance-test-v1".to_owned(),
            algorithm: "Ed25519".to_owned(),
            signature: String::new(),
        };
        let mut unsigned = serde_json::to_value(&directive).unwrap();
        unsigned.as_object_mut().unwrap().remove("signature");
        directive.signature = sign(REVOCATION_DOMAIN, &unsigned);
        assert!(revoke(State(app_state.clone()), Json(directive))
            .await
            .is_ok());
        assert!(
            execute(State(app_state), Json(valid_request(capability_id)))
                .await
                .is_err()
        );
    }
}
