import pytest
from noosfera_core.agent.audit_anchor import AuditIntegrityError, merkle_root


def test_merkle_root_is_deterministic_and_sensitive_to_order() -> None:
    receipts = ["11" * 32, "22" * 32, "33" * 32]
    assert merkle_root(receipts) == merkle_root(receipts)
    assert merkle_root(receipts) != merkle_root(list(reversed(receipts)))


def test_empty_audit_cannot_be_anchored() -> None:
    with pytest.raises(AuditIntegrityError):
        merkle_root([])
