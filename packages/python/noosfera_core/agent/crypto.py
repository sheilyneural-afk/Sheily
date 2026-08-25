"""Firmas Ed25519 con separación de dominio y JSON canónico."""

from __future__ import annotations

import base64
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from noosfera_core.hashing import canonical_bytes


class SignatureRejected(ValueError):
    pass


def _decode_key(value: str, *, length: int = 32) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise ValueError("key must be canonical base64") from exc
    if len(decoded) != length:
        raise ValueError(f"key must contain exactly {length} bytes")
    return decoded


def signing_payload(domain: str, value: dict[str, Any]) -> bytes:
    if not domain or "\x00" in domain:
        raise ValueError("signature domain is invalid")
    return domain.encode("ascii") + b"\x00" + canonical_bytes(value)


class Ed25519Signer:
    def __init__(self, private_key_b64: str, *, key_id: str) -> None:
        self.key_id = key_id
        self._private_key = Ed25519PrivateKey.from_private_bytes(_decode_key(private_key_b64))

    def sign(self, domain: str, value: dict[str, Any]) -> str:
        raw = self._private_key.sign(signing_payload(domain, value))
        return base64.b64encode(raw).decode("ascii")

    def public_key_b64(self) -> str:
        raw = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw).decode("ascii")


class Ed25519Verifier:
    def __init__(self, public_key_b64: str, *, key_id: str) -> None:
        self.key_id = key_id
        self._public_key = Ed25519PublicKey.from_public_bytes(_decode_key(public_key_b64))

    def verify(self, domain: str, value: dict[str, Any], signature: str, key_id: str) -> None:
        if key_id != self.key_id:
            raise SignatureRejected("untrusted signing key")
        try:
            raw_signature = base64.b64decode(signature, validate=True)
            self._public_key.verify(raw_signature, signing_payload(domain, value))
        except (ValueError, InvalidSignature) as exc:
            raise SignatureRejected("signature verification failed") from exc
