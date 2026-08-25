from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def module_files() -> list[Path]:
    index = yaml.safe_load((ROOT / "registry/modules/index.yaml").read_text())
    excluded = set(index["discovery"].get("exclude", []))
    return [
        path
        for path in sorted(ROOT.glob(index["discovery"]["pattern"]))
        if path.relative_to(ROOT).as_posix() not in excluded
    ]


def test_all_discovered_modules_are_unique_without_a_numeric_ceiling() -> None:
    modules: list[str] = []
    for path in module_files():
        modules.extend(item["id"] for item in yaml.safe_load(path.read_text())["modules"])
    assert modules
    assert len(modules) == len(set(modules))
    index = yaml.safe_load((ROOT / "registry/modules/index.yaml").read_text())
    assert "expected_module_count" not in index


def test_every_family_has_a_service() -> None:
    services = yaml.safe_load((ROOT / "registry/services.yaml").read_text())["services"]
    discovered_families = {yaml.safe_load(path.read_text())["family"] for path in module_files()}
    assert {item["family"] for item in services} == discovered_families


def test_generated_counts_match_discovery() -> None:
    maturity = yaml.safe_load((ROOT / "registry/module-maturity.yaml").read_text())
    module_count = sum(len(yaml.safe_load(path.read_text())["modules"]) for path in module_files())
    provider_count = sum(
        len(yaml.safe_load(path.read_text()).get("providers", []))
        for path in (ROOT / "services").glob("*/service.yaml")
    )
    assert maturity["counts"]["modules_discovered"] == module_count
    assert maturity["counts"]["providers_registered"] == provider_count
