"""Autoridad de identidad y consentimiento con comprobantes Ed25519."""

from __future__ import annotations

import base64
import json
import secrets
import time
from datetime import timedelta
from typing import Any, Literal, Protocol, cast

import httpx

from noosfera_core.agent.auth import AuthenticationError
from noosfera_core.agent.crypto import Ed25519Signer, Ed25519Verifier
from noosfera_core.agent.models import (
    ApprovalReceipt,
    Principal,
    TokenResponse,
    new_id,
    utc_now,
)

ACCESS_TOKEN_DOMAIN = "noosfera.identity.access-token.v1"  # noqa: S105 -- protocol domain
APPROVAL_DOMAIN = "noosfera.identity.approval.v1"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class IdentityGateway(Protocol):
    name: str

    async def health(self) -> bool: ...

    async def login(self, username: str, password: str) -> TokenResponse: ...

    def verify_access_token(self, token: str) -> Principal: ...

    async def approve(
        self,
        *,
        token: str,
        mission_id: str,
        plan_hash: str,
        approved: bool,
        remember_result: bool,
        reason: str,
    ) -> ApprovalReceipt: ...


class IdentityAuthority:
    name = "ed25519-identity-authority"

    def __init__(
        self,
        *,
        username: str,
        password: str,
        signer: Ed25519Signer,
        token_ttl_seconds: int,
        approval_ttl_seconds: int = 300,
    ) -> None:
        self.username = username
        self._password = password
        self.signer = signer
        self.verifier = Ed25519Verifier(signer.public_key_b64(), key_id=signer.key_id)
        self.token_ttl_seconds = token_ttl_seconds
        self.approval_ttl_seconds = approval_ttl_seconds

    async def health(self) -> bool:
        return True

    async def login(self, username: str, password: str) -> TokenResponse:
        valid = secrets.compare_digest(username, self.username) and secrets.compare_digest(
            password, self._password
        )
        if not valid:
            raise AuthenticationError("invalid credentials")
        now = int(time.time())
        payload: dict[str, Any] = {
            "sub": f"urn:noosfera:identity:{self.username}",
            "username": self.username,
            "role": "admin",
            "iat": now,
            "exp": now + self.token_ttl_seconds,
            "nonce": secrets.token_hex(16),
            "key_id": self.signer.key_id,
        }
        encoded = _b64encode(json.dumps(payload, sort_keys=True).encode("utf-8"))
        signature = self.signer.sign(ACCESS_TOKEN_DOMAIN, payload)
        return TokenResponse(
            access_token=f"{encoded}.{signature}",
            expires_in=self.token_ttl_seconds,
            user_id=str(payload["sub"]),
            role="admin",
        )

    def verify_access_token(self, token: str) -> Principal:
        try:
            encoded, signature = token.split(".", 1)
            payload = json.loads(_b64decode(encoded))
            if not isinstance(payload, dict):
                raise AuthenticationError("malformed token")
            self.verifier.verify(
                ACCESS_TOKEN_DOMAIN, payload, signature, str(payload.get("key_id", ""))
            )
            if int(payload["exp"]) <= int(time.time()):
                raise AuthenticationError("token expired")
            role = str(payload["role"])
            if role not in {"user", "operator", "admin"}:
                raise AuthenticationError("invalid token role")
            validated_role = cast(Literal["user", "operator", "admin"], role)
            return Principal(
                user_id=str(payload["sub"]),
                username=str(payload["username"]),
                role=validated_role,
            )
        except AuthenticationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AuthenticationError("malformed or invalid token") from exc

    async def approve(
        self,
        *,
        token: str,
        mission_id: str,
        plan_hash: str,
        approved: bool,
        remember_result: bool,
        reason: str,
    ) -> ApprovalReceipt:
        principal = self.verify_access_token(token)
        now = utc_now()
        body = {
            "id": new_id("approval"),
            "user_id": principal.user_id,
            "mission_id": mission_id,
            "plan_hash": plan_hash,
            "approved": approved,
            "remember_result": remember_result,
            "reason": reason,
            "issued_at": now,
            "expiry": now + timedelta(seconds=self.approval_ttl_seconds),
            "key_id": self.signer.key_id,
            "algorithm": "Ed25519",
        }
        serializable = ApprovalReceipt.model_validate({**body, "signature": "pending"})
        payload = serializable.model_dump(mode="json", exclude={"signature"})
        return serializable.model_copy(
            update={"signature": self.signer.sign(APPROVAL_DOMAIN, payload)}
        )


class RemoteIdentityClient:
    name = "remote-identity-service"

    def __init__(
        self,
        base_url: str,
        *,
        public_key_b64: str,
        key_id: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.verifier = Ed25519Verifier(public_key_b64, key_id=key_id)

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/health/ready")
                return response.is_success
        except httpx.HTTPError:
            return False

    async def login(self, username: str, password: str) -> TokenResponse:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/v1/auth/login",
                json={"username": username, "password": password},
            )
        if response.status_code != 200:
            raise AuthenticationError("invalid credentials or identity service unavailable")
        return TokenResponse.model_validate(response.json())

    def verify_access_token(self, token: str) -> Principal:
        try:
            encoded, signature = token.split(".", 1)
            payload = json.loads(_b64decode(encoded))
            self.verifier.verify(
                ACCESS_TOKEN_DOMAIN, payload, signature, str(payload.get("key_id", ""))
            )
            if int(payload["exp"]) <= int(time.time()):
                raise AuthenticationError("token expired")
            return Principal.model_validate(
                {
                    "user_id": payload["sub"],
                    "username": payload["username"],
                    "role": payload["role"],
                }
            )
        except AuthenticationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AuthenticationError("malformed or invalid token") from exc

    async def approve(
        self,
        *,
        token: str,
        mission_id: str,
        plan_hash: str,
        approved: bool,
        remember_result: bool,
        reason: str,
    ) -> ApprovalReceipt:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/v1/approvals",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "mission_id": mission_id,
                    "plan_hash": plan_hash,
                    "approved": approved,
                    "remember_result": remember_result,
                    "reason": reason,
                },
            )
        if response.status_code != 201:
            raise AuthenticationError("identity service rejected approval")
        return ApprovalReceipt.model_validate(response.json())
