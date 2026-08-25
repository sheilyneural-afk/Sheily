"""El proveedor local no puede desviarse silenciosamente a un host remoto."""

import pytest
from noosfera_core.agent.model_provider import assert_local_endpoint


@pytest.mark.parametrize(
    "endpoint",
    ["https://models.example.com", "http://10.0.0.8:11434", "http://remote:11434"],
)
def test_remote_model_endpoints_are_denied_by_default(endpoint: str) -> None:
    with pytest.raises(ValueError, match="remote model endpoint"):
        assert_local_endpoint(endpoint, allow_remote=False)


@pytest.mark.parametrize(
    "endpoint",
    ["http://localhost:11434", "http://127.0.0.1:11434", "http://ollama:11434"],
)
def test_known_local_model_endpoints_are_allowed(endpoint: str) -> None:
    assert_local_endpoint(endpoint, allow_remote=False)
