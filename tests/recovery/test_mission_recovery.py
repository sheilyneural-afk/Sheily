import pytest
from noosfera_core.mission import InvalidTransition, transition


def test_paused_mission_may_revert() -> None:
    assert transition("paused", "reversion") == "reversion"


def test_closed_mission_cannot_restart_execution() -> None:
    with pytest.raises(InvalidTransition):
        transition("closed", "execution")
