#!/usr/bin/env python3
"""Ejecuta casos de contrato contra el modelo local configurado."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from noosfera_core.agent.model_provider import DeterministicLocalModel, OllamaModel
from noosfera_core.config import Settings

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "model-contract-cases.json"


def load_cases() -> list[dict[str, Any]]:
    value = json.loads(CASES.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("evaluation cases must be a JSON array of objects")
    return value


async def run(provider: str) -> int:
    settings = Settings()
    if provider == "deterministic":
        model = DeterministicLocalModel()
    else:
        model = OllamaModel(
            base_url=settings.model_base_url,
            model_name=settings.model_name,
            timeout_seconds=settings.model_timeout_seconds,
            max_input_chars=settings.model_max_input_chars,
            context_tokens=settings.model_context_tokens,
            output_tokens=settings.model_output_tokens,
            allow_remote=settings.model_allow_remote,
        )
    failures: list[str] = []
    for case in load_cases():
        case_id = str(case["id"])
        try:
            plan = await model.plan(str(case["prompt"]), has_documents=bool(case["has_documents"]))
            if plan.tool != case["expected_tool"]:
                failures.append(
                    f"{case_id}: expected {case['expected_tool']}, received {plan.tool}"
                )
            if plan.requires_documents != bool(case["has_documents"]):
                failures.append(f"{case_id}: document scope mismatch")
            print(f"PASS {case_id}: {plan.tool}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{case_id}: {exc}")
            print(f"FAIL {case_id}: {exc}")
    if failures:
        print("\nEvaluation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"\n{len(load_cases())} model-contract cases passed with {model.model_name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["ollama", "deterministic"], default="ollama")
    arguments = parser.parse_args()
    return asyncio.run(run(arguments.provider))


if __name__ == "__main__":
    raise SystemExit(main())
