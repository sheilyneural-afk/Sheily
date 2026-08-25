#!/usr/bin/env python3
"""Valida todos los esquemas y los ejemplos declarados."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "tests" / "fixtures" / "contracts"


def validator(schema_name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    resources = {
        loaded["$id"]: Resource.from_contents(loaded)
        for path in SCHEMAS.glob("*.json")
        if "$id" in (loaded := json.loads(path.read_text(encoding="utf-8")))
    }
    registry = Registry().with_resources(resources.items())
    return Draft202012Validator(schema, registry=registry)


def main() -> int:
    errors: list[str] = []
    for schema_path in SCHEMAS.glob("*.json"):
        try:
            Draft202012Validator.check_schema(json.loads(schema_path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{schema_path.name}: {exc}")
    for fixture_path in FIXTURES.glob("*.valid.json"):
        schema_name = fixture_path.name.removesuffix(".valid.json") + ".schema.json"
        try:
            value = json.loads(fixture_path.read_text(encoding="utf-8"))
            validator(schema_name).validate(value)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{fixture_path.name}: {exc}")
    for fixture_path in FIXTURES.glob("*.invalid.json"):
        schema_name = fixture_path.name.removesuffix(".invalid.json") + ".schema.json"
        value = json.loads(fixture_path.read_text(encoding="utf-8"))
        if validator(schema_name).is_valid(value):
            errors.append(f"{fixture_path.name}: expected invalid fixture to fail")
    if errors:
        print("schema validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("schema validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
