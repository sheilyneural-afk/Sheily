"""Pruebas de autenticación local y rechazo de manipulación."""

import pytest
from noosfera_core.agent.auth import AuthenticationError, AuthService


def auth_service() -> AuthService:
    return AuthService(
        username="owner",
        password="correct-horse-battery-staple",  # noqa: S106 -- test credential
        secret="test-token-secret-with-at-least-32-characters",  # noqa: S106
        token_ttl_seconds=60,
    )


def test_local_login_round_trip() -> None:
    service = auth_service()
    token = service.login("owner", "correct-horse-battery-staple")

    principal = service.verify(token.access_token)

    assert principal.username == "owner"
    assert principal.role == "admin"


def test_invalid_password_and_tampered_token_are_rejected() -> None:
    service = auth_service()
    with pytest.raises(AuthenticationError):
        service.login("owner", "incorrect")

    token = service.login("owner", "correct-horse-battery-staple").access_token
    with pytest.raises(AuthenticationError):
        service.verify(f"{token}tampered")
