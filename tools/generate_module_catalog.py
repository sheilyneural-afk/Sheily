#!/usr/bin/env python3
"""Imprime una tabla Markdown reproducible del registro de módulos."""

from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
print("| Módulo | Servicio | Responsabilidad |")
print("|---|---|---|")
for path in sorted((root / "registry/modules").glob("*.yaml")):
    if path.name == "index.yaml":
        continue
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    for module in payload["modules"]:
        identity = f"{module['id']} · {module['name']}"
        print(f"| {identity} | {payload['service']} | {module['responsibility']} |")
