#!/usr/bin/env python3
"""Genera madurez desde módulos y proveedores descubiertos, sin cifras fijas."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "registry" / "module-maturity.yaml"
STATE_RANK = {
    "declared": 0,
    "implemented": 1,
    "integrated": 2,
    "verified": 3,
    "production-ready": 4,
}


def discover_module_files() -> list[Path]:
    index = yaml.safe_load((ROOT / "registry/modules/index.yaml").read_text(encoding="utf-8"))
    discovery = index["discovery"]
    excluded = set(discovery.get("exclude", []))
    return [
        path
        for path in sorted(ROOT.glob(discovery["pattern"]))
        if path.relative_to(ROOT).as_posix() not in excluded
    ]


def main() -> None:
    modules: dict[str, dict[str, Any]] = {}
    for path in discover_module_files():
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        for module in payload["modules"]:
            modules[module["id"]] = {
                "id": module["id"],
                "family": payload["family"],
                "state": "declared",
                "providers": [],
                "evidence": [path.relative_to(ROOT).as_posix()],
            }

    provider_count = 0
    for manifest_path in sorted((ROOT / "services").glob("*/service.yaml")):
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        for provider in manifest.get("providers", []):
            provider_count += 1
            provider_view = {
                "id": provider["id"],
                "service": manifest["id"],
                "runtime": manifest["runtime"],
                "endpoint": provider["endpoint"],
                "methods": provider["methods"],
                "capabilities": provider["capabilities"],
            }
            for module_id in provider["modules"]:
                entry = modules[module_id]
                entry["providers"].append(copy.deepcopy(provider_view))
                if STATE_RANK[provider["maturity"]] > STATE_RANK[entry["state"]]:
                    entry["state"] = provider["maturity"]
                for evidence in [
                    manifest_path.relative_to(ROOT).as_posix(),
                    *provider["evidence"],
                ]:
                    if evidence not in entry["evidence"]:
                        entry["evidence"].append(evidence)

    entries = sorted(modules.values(), key=lambda item: item["id"])
    document = {
        "version": 2,
        "counts": {
            "modules_discovered": len(entries),
            "providers_registered": provider_count,
            "modules_with_providers": sum(bool(item["providers"]) for item in entries),
            "modules_declared_only": sum(not item["providers"] for item in entries),
        },
        "states": list(STATE_RANK),
        "runtime_note": (
            "registered providers are claims; /v1/modules is authoritative for loaded routes"
        ),
        "modules": entries,
    }
    OUTPUT.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
