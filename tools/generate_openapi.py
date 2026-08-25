#!/usr/bin/env python3
"""Regenera el contrato OpenAPI desde la API de Experience."""

from __future__ import annotations

from pathlib import Path

import yaml
from noosfera_core.agent.api import create_agent_app

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    app = create_agent_app(ROOT / "services/experience-service/service.yaml")
    document = app.openapi()
    (ROOT / "api/openapi.yaml").write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
