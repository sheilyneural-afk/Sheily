from noosfera_core.hashing import canonical_hash


def test_canonical_hash_ignores_dictionary_order() -> None:
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})
