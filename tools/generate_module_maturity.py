#!/usr/bin/env python3
"""Genera el inventario explícito de madurez de los 105 módulos."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "registry" / "module-maturity.yaml"

INTEGRATED = {
    "EXP-01": "API de conversación y documentos",
    "EXP-05": "consentimiento firmado ligado a misión/plan",
    "IDN-01": "identidad local Ed25519 y tokens verificables",
    "IDN-04": "comprobante de voluntad actual firmado",
    "MEM-01": "ciclo cognitivo como memoria de trabajo",
    "MEM-02": "memoria personal consentida con borrado",
    "MEM-04": "creencias semánticas consolidadas por procedencia",
    "MEM-05": "hashes de contexto, evidencia y recibos",
    "MEM-06": "retención y borrado lógico consentido",
    "COG-08": "frontera de acciones con crítico y abstención",
    "COG-10": "incertidumbre y suficiencia de evidencia explícitas",
    "AGY-01": "petición convertida en plan estructurado",
    "AGY-03": "objetivo descompuesto en pasos y criterios",
    "AGY-04": "plan causal generado fuera del LLM",
    "AGY-06": "máquina de estados de misión persistente",
    "AGY-07": "validación de dependencias, alcance y presupuestos",
    "AGY-08": "vinculación hash de objetivo, contexto y plan",
    "GOV-01": "políticas constitucionales OPA",
    "GOV-03": "clasificación de riesgo OPA",
    "GOV-05": "mandato ligado a identidad y consentimiento",
    "GOV-06": "emisor independiente de capacidades Ed25519",
    "GOV-11": "directivas de parada firmadas y monotónicas",
    "EXE-01": "unión plan-capacidad-argumentos en Rust",
    "EXE-03": "presupuestos validados por el ejecutor",
    "EXE-05": "monitores internos fail-closed",
    "EXE-08": "safe-stop durable verificado por clave pública",
    "AUD-01": "registro append-only, cadena y anclas Merkle firmadas",
    "AUD-02": "traza intención-plan-consentimiento-capacidad-ejecución",
}

VERIFIED = {
    "AGY-04",
    "AGY-06",
    "GOV-06",
    "GOV-11",
    "EXE-01",
    "EXE-03",
    "EXE-08",
}


def main() -> None:
    index = yaml.safe_load((ROOT / "registry/modules/index.yaml").read_text(encoding="utf-8"))
    entries: list[dict[str, object]] = []
    for family, relative in index["families"].items():
        payload = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
        for module in payload["modules"]:
            module_id = module["id"]
            state = "hosted"
            evidence: list[str] = [f"services/{payload['service']}/service.yaml"]
            if module_id in INTEGRATED:
                state = "verified" if module_id in VERIFIED else "integrated"
                evidence.append(INTEGRATED[module_id])
            entries.append(
                {
                    "id": module_id,
                    "family": family,
                    "state": state,
                    "evidence": evidence,
                }
            )
    document = {
        "version": 1,
        "states": [
            "declared",
            "hosted",
            "implemented",
            "integrated",
            "verified",
            "production-ready",
        ],
        "modules": entries,
    }
    OUTPUT.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
