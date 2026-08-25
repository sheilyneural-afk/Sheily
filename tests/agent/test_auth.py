"""Pruebas de autenticación local y rechazo de manipulación."""

import pytest
from noosfera_core.agent.auth import AuthenticationError
from noosfera_core.agent.crypto import Ed25519Signer
from noosfera_core.agent.identity import IdentityAuthority


def auth_service() -> IdentityAuthority:
    return IdentityAuthority(
        username="owner",
        password="correct-horse-battery-staple",  # noqa: S106 -- test credential
        signer=Ed25519Signer(
            "fECcWuqB0rjSdD2t6ADoVCOkG6Or8bG/mHeytU39bHs=",  # noqa: S106
            key_id="identity-local-v1",
        ),
        token_ttl_seconds=60,
    )


@pytest.mark.asyncio
async def test_local_login_round_trip() -> None:
    service = auth_service()
    token = await service.login("owner", "correct-horse-battery-staple")

    principal = service.verify_access_token(token.access_token)

    assert principal.username == "owner"
    assert principal.role == "admin"


@pytest.mark.asyncio
async def test_invalid_password_and_tampered_token_are_rejected() -> None:
    service = auth_service()
    with pytest.raises(AuthenticationError):
        await service.login("owner", "incorrect")

    token = (await service.login("owner", "correct-horse-battery-staple")).access_token
    with pytest.raises(AuthenticationError):
        service.verify_access_token(f"{token}tampered")
