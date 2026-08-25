from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_exactly_105_unique_modules() -> None:
    modules: list[str] = []
    for path in (ROOT / "registry/modules").glob("*.yaml"):
        if path.name != "index.yaml":
            modules.extend(item["id"] for item in yaml.safe_load(path.read_text())["modules"])
    assert len(modules) == 105
    assert len(set(modules)) == 105


def test_every_family_has_a_service() -> None:
    services = yaml.safe_load((ROOT / "registry/services.yaml").read_text())["services"]
    assert {item["family"] for item in services} == {
        "EXP",
        "IDN",
        "MEM",
        "PER",
        "COG",
        "AGY",
        "GOV",
        "EXE",
        "FED",
        "SEC",
        "AUD",
        "EVO",
        "TMP",
        "RES",
    }
