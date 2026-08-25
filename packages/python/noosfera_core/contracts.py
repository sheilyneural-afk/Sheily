"""Validación de documentos contra el registro canónico de esquemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class ContractRegistry:
    def __init__(self, schema_root: Path) -> None:
        self.schema_root = schema_root.resolve()
        self._validators: dict[str, Draft202012Validator] = {}

    def _validator(self, schema_name: str) -> Draft202012Validator:
        cached = self._validators.get(schema_name)
        if cached is not None:
            return cached
        path = self.schema_root / schema_name
        schema = json.loads(path.read_text(encoding="utf-8"))
        resources = {
            loaded["$id"]: Resource.from_contents(loaded)
            for schema_path in self.schema_root.glob("*.json")
            if "$id" in (loaded := json.loads(schema_path.read_text(encoding="utf-8")))
        }
        registry = Registry().with_resources(resources.items())
        validator = Draft202012Validator(schema, registry=registry)
        self._validators[schema_name] = validator
        return validator

    def validate(self, schema_name: str, value: Any) -> None:
        self._validator(schema_name).validate(value)
