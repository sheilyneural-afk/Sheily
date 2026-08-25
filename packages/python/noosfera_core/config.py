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
    governance_backend: str = "opa"
    execution_backend: str = "rust"
    execution_url: str = "http://localhost:8108"
    model_provider: str = "ollama"
    model_base_url: str = "http://localhost:11434"
    model_name: str = "qwen3:8b"
    model_allow_remote: bool = False
    model_timeout_seconds: float = 120.0
    model_max_input_chars: int = 200_000
    model_context_tokens: int = 32_768
    model_output_tokens: int = 4_096
    max_document_bytes: int = 5_000_000
    max_output_bytes: int = 250_000
    capability_ttl_seconds: int = 300
    local_username: str = "sheily"
    local_password: str = Field(default="change-me-local", repr=False)
    token_secret: str = Field(default="local-token-secret-change-me-32-characters", repr=False)
    capability_secret: str = Field(default="local-capability-secret-change-me-32-chars", repr=False)
    token_ttl_seconds: int = 3600
    cors_origins: str = "http://localhost:3001,http://localhost:3002"

    def assert_production_safe(self) -> None:
        if self.env == "production" and not self.signing_key_ref:
            raise ValueError("production requires a non-empty signing_key_ref")
        if self.env == "production" and "localhost" in self.database_url:
            raise ValueError("production may not use the local database")
        if self.env == "production" and self.model_provider == "deterministic":
            raise ValueError("production may not use the deterministic model")
        if self.env == "production" and self.local_password == "change-me-local":  # noqa: S105
            raise ValueError("production requires a non-default local password")
        if self.env == "production" and "change-me" in self.token_secret:
            raise ValueError("production requires a non-default token secret")
        if self.env == "production" and "change-me" in self.capability_secret:
            raise ValueError("production requires a non-default capability secret")
