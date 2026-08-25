"""Autenticación local con tokens HMAC de corta duración."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Literal, cast

from noosfera_core.agent.models import Principal, TokenResponse


class AuthenticationError(ValueError):
    pass


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class AuthService:
    def __init__(
        self,
        *,
        username: str,
        password: str,
        secret: str,
        token_ttl_seconds: int,
    ) -> None:
        if len(secret) < 32:
            raise ValueError("token secret must contain at least 32 characters")
        self.username = username
        self._password = password
        self._secret = secret.encode("utf-8")
        self.token_ttl_seconds = token_ttl_seconds

    def login(self, username: str, password: str) -> TokenResponse:
        valid = secrets.compare_digest(username, self.username) and secrets.compare_digest(
            password, self._password
        )
        if not valid:
            raise AuthenticationError("invalid credentials")
        now = int(time.time())
        principal = Principal(
            user_id=f"urn:noosfera:identity:{self.username}",
            username=self.username,
            role="admin",
        )
        payload: dict[str, Any] = {
            "sub": principal.user_id,
            "username": principal.username,
            "role": principal.role,
            "iat": now,
            "exp": now + self.token_ttl_seconds,
            "nonce": secrets.token_hex(8),
        }
        encoded = _b64encode(json.dumps(payload, sort_keys=True).encode("utf-8"))
        signature = _b64encode(hmac.digest(self._secret, encoded.encode("ascii"), "sha256"))
        return TokenResponse(
            access_token=f"{encoded}.{signature}",
            expires_in=self.token_ttl_seconds,
            user_id=principal.user_id,
            role=principal.role,
        )

    def verify(self, token: str) -> Principal:
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected_signature = _b64encode(
                hmac.digest(self._secret, encoded.encode("ascii"), "sha256")
            )
            if not secrets.compare_digest(supplied_signature, expected_signature):
                raise AuthenticationError("invalid token signature")
            payload = json.loads(_b64decode(encoded))
            if int(payload["exp"]) <= int(time.time()):
                raise AuthenticationError("token expired")
            raw_role = str(payload["role"])
            if raw_role not in {"user", "operator", "admin"}:
                raise AuthenticationError("invalid token role")
            role = cast(Literal["user", "operator", "admin"], raw_role)
            return Principal(
                user_id=str(payload["sub"]),
                username=str(payload["username"]),
                role=role,
            )
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            if isinstance(exc, AuthenticationError):
                raise
            raise AuthenticationError("malformed token") from exc


def sign_capability(capability: dict[str, Any], secret: str) -> str:
    canonical = json.dumps(capability, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
