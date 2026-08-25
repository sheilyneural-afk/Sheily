#!/usr/bin/env python3
"""Regenera el cierre exacto de archivos sin alterar las reglas de propiedad."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "FILE_MANIFEST.yaml"
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


def repository_files() -> list[str]:
    files: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.name == ".env":
            continue
        if path.parts[-2:] == ("artifacts", "runtime"):
            continue
        files.append(path.relative_to(ROOT).as_posix())
    return sorted(files)


def main() -> None:
    existing = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    files = repository_files()
    document = {
        "version": existing.get("version", 1),
        "architecture_version": "0.3.0",
        "expected_file_count": len(files),
        "closure": existing["closure"],
        "ownership_rules": existing["ownership_rules"],
        "files": files,
    }
    MANIFEST.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
