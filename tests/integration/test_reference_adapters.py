import pytest

from adapters.reference.deny_policy import DenyPolicy
from adapters.reference.in_memory_ledger import InMemoryLedger
from adapters.reference.null_actuator import NullActuator


@pytest.mark.asyncio
async def test_reference_stack_cannot_change_world() -> None:
    policy = await DenyPolicy().evaluate("test", {})
    action = await NullActuator().execute({"operation": "dry-run"})
    receipt = await InMemoryLedger().append({"type": "reference-test"})
    assert policy["allow"] is False
    assert action["accepted"] is False
    assert len(receipt["receipt_hash"]) == 64
