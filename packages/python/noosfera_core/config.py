"""Configuración estricta y sin secretos por defecto."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración común de una instancia de servicio."""

    model_config = SettingsConfigDict(env_prefix="NOOSFERA_", env_file=".env", extra="ignore")

    env: str = "local"
    node_id: str = "node-local-development"
    log_level: str = "INFO"
    database_url: str = "postgresql://noosfera:noosfera@localhost:5432/noosfera"
    nats_url: str = "nats://localhost:4222"
    object_store_endpoint: str = "http://localhost:9000"
    object_store_bucket: str = "noosfera-evidence"
    opa_url: str = "http://localhost:8181"
    otlp_endpoint: str = "http://localhost:4317"
    signing_key_ref: str = Field(default="", repr=False)
    storage_backend: str = "postgres"
    event_backend: str = "nats"
    identity_backend: str = "remote"
    cognition_backend: str = "remote"
    agency_backend: str = "remote"
    governance_backend: str = "remote"
    execution_backend: str = "rust"
    identity_url: str = "http://localhost:8102"
    cognition_url: str = "http://localhost:8105"
    agency_url: str = "http://localhost:8106"
    governance_url: str = "http://localhost:8107"
    execution_url: str = "http://localhost:8108"
    audit_url: str = "http://localhost:8111"
    document_verification_backend: str = "remote"
    model_provider: str = "ollama"
    model_base_url: str = "http://localhost:11434"
    model_name: str = "qwen3:8b"
    model_allow_remote: bool = False
    model_timeout_seconds: float = 600.0
    model_max_concurrency: int = Field(default=1, ge=1, le=8)
    model_max_input_chars: int = 200_000
    model_document_max_blocks: int = Field(default=32, ge=8, le=200)
    model_context_tokens: int = 32_768
    model_output_tokens: int = 4_096
    self_model_registry_path: str = "registry"
    runtime_registry_urls: str = ""
    runtime_registry_timeout_seconds: float = 1.0
    self_model_cache_seconds: float = 5.0
    max_document_bytes: int = 5_000_000
    max_output_bytes: int = 250_000
    capability_ttl_seconds: int = 300
    local_username: str = "sheily"
    local_password: str = Field(default="change-me-local", repr=False)
    identity_key_id: str = "identity-local-v1"
    identity_private_key_b64: str = Field(default="", repr=False)
    identity_public_key_b64: str = "exnDIf2q8iXSzoTw0cuNx3YEmeVS7DNcVIIB7pPPcHg="
    agency_key_id: str = "agency-local-v1"
    agency_private_key_b64: str = Field(default="", repr=False)
    agency_public_key_b64: str = "QGNyLWPX7BkNlh+cnFMvTRdT4MixG5cPhcRuBD0DUq0="
    governance_key_id: str = "governance-local-v1"
    governance_private_key_b64: str = Field(default="", repr=False)
    governance_public_key_b64: str = "IrJbc2jDxJLC4UnngrXD4MAMz1PCOkfvSPAu064Vg3c="
    audit_key_id: str = "audit-local-v1"
    audit_private_key_b64: str = Field(default="", repr=False)
    audit_public_key_b64: str = "TdIFu4tTVfVgNGcq5iU5XdNNOI+CZyeHNlQkUyviV2g="
    internal_service_token: str = Field(
        default="local-internal-service-token-change-me", repr=False
    )
    token_ttl_seconds: int = 3600
    cors_origins: str = "http://localhost:3001,http://localhost:3002"

    def assert_production_safe(self) -> None:
        if self.env == "production" and not self.signing_key_ref:
            raise ValueError("production requires a non-empty signing_key_ref")
        if self.env == "production" and "localhost" in self.database_url:
            raise ValueError("production may not use the local database")
        if self.env == "production" and self.model_provider == "deterministic":
            raise ValueError("production may not use the deterministic model")
        if self.env == "production" and (
            self.local_password in {"change-me-local", "sheily"}  # noqa: S105
            or len(self.local_password) < 12
        ):
            raise ValueError("production requires a strong non-default local password")
        if self.env == "production" and "change-me" in self.internal_service_token:
            raise ValueError("production requires a non-default internal service token")
        if self.env == "production" and self.governance_backend != "remote":
            raise ValueError("production experience service requires remote governance")
        if self.env == "production" and self.agency_backend != "remote":
            raise ValueError("production experience service requires remote agency")

    def assert_identity_safe(self) -> None:
        if not self.identity_private_key_b64:
            raise ValueError("identity service requires NOOSFERA_IDENTITY_PRIVATE_KEY_B64")
        if self.env == "production" and (
            self.local_password in {"change-me-local", "sheily"}  # noqa: S105
            or len(self.local_password) < 12
        ):
            raise ValueError("production requires a strong non-default local password")

    def assert_agency_safe(self) -> None:
        if not self.agency_private_key_b64:
            raise ValueError("agency service requires NOOSFERA_AGENCY_PRIVATE_KEY_B64")

    def assert_governance_safe(self) -> None:
        if not self.governance_private_key_b64:
            raise ValueError("governance requires NOOSFERA_GOVERNANCE_PRIVATE_KEY_B64")

    def assert_audit_safe(self) -> None:
        if not self.audit_private_key_b64:
            raise ValueError("audit service requires NOOSFERA_AUDIT_PRIVATE_KEY_B64")
