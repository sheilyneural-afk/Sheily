import pytest
from noosfera_core.mission import InvalidTransition, transition


def test_valid_transition() -> None:
    assert transition("received", "compiled") == "compiled"


def test_execution_cannot_skip_authorization() -> None:
    with pytest.raises(InvalidTransition):
        transition("analysis", "execution")
