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

    def assert_production_safe(self) -> None:
        if self.env == "production" and not self.signing_key_ref:
            raise ValueError("production requires a non-empty signing_key_ref")
        if self.env == "production" and "localhost" in self.database_url:
            raise ValueError("production may not use the local database")
