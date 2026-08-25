"""Núcleo compartido del plano de control de Noosfera."""

from noosfera_core.hashing import canonical_hash
from noosfera_core.manifest import ServiceManifest, load_service_manifest

__all__ = ["ServiceManifest", "canonical_hash", "load_service_manifest"]
__version__ = "0.2.0"
