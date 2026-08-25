#!/usr/bin/env python3
"""Verifica cierre estructural: archivos, módulos, servicios, contratos y referencias."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "target",
}


class Verification:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def actual_files() -> set[str]:
    result: set[str] = set()
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.parts[-2:] == ("artifacts", "runtime"):
            continue
        result.add(path.relative_to(ROOT).as_posix())
    return result


def verify_file_manifest(check: Verification) -> None:
    path = ROOT / "FILE_MANIFEST.yaml"
    check.require(path.exists(), "FILE_MANIFEST.yaml is missing")
    if not path.exists():
        return
    manifest = load_yaml(path)
    listed = set(manifest.get("files", []))
    present = actual_files()
    check.require(
        len(listed) == manifest.get("expected_file_count"),
        "FILE_MANIFEST expected_file_count does not match its unique entries",
    )
    check.require(len(listed) == len(manifest.get("files", [])), "FILE_MANIFEST has duplicates")
    for missing in sorted(listed - present):
        check.errors.append(f"manifest references missing file: {missing}")
    for unlisted in sorted(present - listed):
        check.errors.append(f"file is not in FILE_MANIFEST: {unlisted}")
    rules = manifest.get("ownership_rules", [])
    for file_name in sorted(listed):
        matching = [
            rule
            for rule in rules
            if file_name == rule.get("path") or file_name.startswith(rule.get("prefix", "\0"))
        ]
        check.require(bool(matching), f"no ownership rule for {file_name}")


def verify_modules_and_services(check: Verification) -> None:
    module_index = load_yaml(ROOT / "registry/modules/index.yaml")
    buses = {item["id"] for item in load_yaml(ROOT / "registry/buses.yaml")["buses"]}
    all_modules: dict[str, dict[str, Any]] = {}
    family_modules: dict[str, set[str]] = {}
    port_pattern = re.compile(r"^[a-z][a-z0-9-]+$")

    for family, relative in module_index["families"].items():
        module_file = ROOT / relative
        check.require(module_file.exists(), f"module family file missing: {relative}")
        if not module_file.exists():
            continue
        payload = load_yaml(module_file)
        check.require(payload["family"] == family, f"family mismatch in {relative}")
        family_modules[family] = set()
        for module in payload["modules"]:
            module_id = module["id"]
            check.require(module_id not in all_modules, f"duplicate module id: {module_id}")
            check.require(
                module_id.startswith(family + "-"), f"module prefix mismatch: {module_id}"
            )
            check.require(bool(module.get("name")), f"module without name: {module_id}")
            check.require(
                bool(module.get("responsibility")), f"module without responsibility: {module_id}"
            )
            check.require(bool(module.get("buses")), f"module without bus: {module_id}")
            for bus in module.get("buses", []):
                check.require(bus in buses, f"unknown bus {bus} in {module_id}")
            for port in module.get("inputs", []) + module.get("outputs", []):
                check.require(
                    bool(port_pattern.fullmatch(port)), f"invalid port name {port} in {module_id}"
                )
            all_modules[module_id] = module
            family_modules[family].add(module_id)

    expected = module_index["expected_module_count"]
    check.require(
        len(all_modules) == expected, f"expected {expected} modules, found {len(all_modules)}"
    )

    services_registry = load_yaml(ROOT / "registry/services.yaml")["services"]
    service_schema = json.loads(
        (ROOT / "schemas/service-manifest.schema.json").read_text(encoding="utf-8")
    )
    service_validator = Draft202012Validator(service_schema)
    check.require(
        len(services_registry) == 14, f"expected 14 services, found {len(services_registry)}"
    )
    seen_families: set[str] = set()
    hosted: set[str] = set()
    for registered in services_registry:
        service_id = registered["id"]
        family = registered["family"]
        seen_families.add(family)
        service_dir = ROOT / "services" / service_id
        required = [
            service_dir / "README.md",
            service_dir / "main.py",
            service_dir / "service.yaml",
            ROOT / "ops/slos" / f"{service_id}.yaml",
            ROOT / "ops/runbooks" / f"{service_id}.md",
            ROOT / "deploy/services" / f"{service_id}.yaml",
        ]
        for required_file in required:
            check.require(
                required_file.exists(),
                f"service artifact missing: {required_file.relative_to(ROOT)}",
            )
        if not (service_dir / "service.yaml").exists():
            continue
        manifest = load_yaml(service_dir / "service.yaml")
        for error in service_validator.iter_errors(manifest):
            check.errors.append(f"invalid service manifest {service_id}: {error.message}")
        check.require(manifest["id"] == service_id, f"service id mismatch: {service_id}")
        check.require(manifest["family"] == family, f"service family mismatch: {service_id}")
        declared = set(manifest["modules"])
        check.require(
            declared == family_modules.get(family, set()),
            f"module ownership mismatch for {service_id}",
        )
        duplicate_hosting = hosted & declared
        check.require(not duplicate_hosting, f"modules hosted twice: {sorted(duplicate_hosting)}")
        hosted |= declared
    check.require(
        seen_families == set(family_modules), "not every module family has exactly one service"
    )
    check.require(hosted == set(all_modules), "not every module is hosted")

    maturity = load_yaml(ROOT / "registry/module-maturity.yaml")
    allowed_states = set(maturity.get("states", []))
    maturity_entries = maturity.get("modules", [])
    maturity_ids = {item.get("id") for item in maturity_entries}
    check.require(
        maturity_ids == set(all_modules),
        "module maturity registry must classify every logical module exactly once",
    )
    check.require(
        len(maturity_ids) == len(maturity_entries), "module maturity registry has duplicates"
    )
    for item in maturity_entries:
        check.require(
            item.get("state") in allowed_states,
            f"invalid maturity state for {item.get('id')}",
        )
        check.require(bool(item.get("evidence")), f"missing maturity evidence for {item.get('id')}")


def verify_contracts_and_policies(check: Verification) -> None:
    for contract in load_yaml(ROOT / "registry/contracts.yaml")["contracts"]:
        for key in ("schema", "proto"):
            path = ROOT / contract[key]
            check.require(
                path.exists(), f"contract {contract['id']} missing {key}: {contract[key]}"
            )
    for policy in load_yaml(ROOT / "registry/policies.yaml")["policies"]:
        path = ROOT / policy["path"]
        check.require(path.exists(), f"policy {policy['id']} missing: {policy['path']}")

    for schema_path in (ROOT / "schemas").glob("*.json"):
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # noqa: BLE001
            check.errors.append(f"invalid JSON schema {schema_path.name}: {exc}")

    local_proto_files = {
        path.relative_to(ROOT / "proto").as_posix() for path in (ROOT / "proto").rglob("*.proto")
    }
    import_pattern = re.compile(r'^import\s+"([^"]+)";', re.MULTILINE)
    for proto_path in (ROOT / "proto").rglob("*.proto"):
        for imported in import_pattern.findall(proto_path.read_text(encoding="utf-8")):
            if imported.startswith("google/protobuf/"):
                continue
            check.require(
                imported in local_proto_files,
                f"missing proto import {imported} from {proto_path.relative_to(ROOT)}",
            )


def verify_markdown_links(check: Verification) -> None:
    link_pattern = re.compile(r"\[[^]]+\]\((?!https?://|#|mailto:)([^)]+)\)")
    for document in ROOT.rglob("*.md"):
        if any(part in IGNORED_PARTS for part in document.parts):
            continue
        text = document.read_text(encoding="utf-8")
        for raw_target in link_pattern.findall(text):
            target = raw_target.split("#", 1)[0].strip("<>")
            if not target:
                continue
            resolved = (document.parent / target).resolve()
            check.require(
                resolved.exists(), f"broken link in {document.relative_to(ROOT)}: {raw_target}"
            )


def main() -> int:
    check = Verification()
    verify_file_manifest(check)
    verify_modules_and_services(check)
    verify_contracts_and_policies(check)
    verify_markdown_links(check)
    if check.errors:
        print(f"repository verification failed with {len(check.errors)} error(s):")
        for error in check.errors:
            print(f"- {error}")
        return 1
    print("repository verification passed")
    print("- file manifest is closed")
    print("- 105 logical modules are hosted exactly once")
    print("- 14 services have manifests, SLOs, runbooks and deployment profiles")
    print("- contracts, policies, proto imports and documentation links are valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
