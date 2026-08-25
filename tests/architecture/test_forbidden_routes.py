from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def service(family: str) -> dict[str, object]:
    for item in yaml.safe_load((ROOT / "registry/services.yaml").read_text())["services"]:
        if item["family"] == family:
            return item
    raise AssertionError(f"missing family {family}")


def manifest(service_id: str) -> dict[str, object]:
    return yaml.safe_load((ROOT / "services" / service_id / "service.yaml").read_text())


def test_cognition_cannot_publish_to_action_bus() -> None:
    cog = manifest(str(service("COG")["id"]))
    assert "BUS-ACT" not in cog["outbound_buses"]
    assert "BUS-AUT" not in cog["outbound_buses"]


def test_agency_cannot_publish_capabilities() -> None:
    agy = manifest(str(service("AGY")["id"]))
    assert "BUS-AUT" not in agy["outbound_buses"]


def test_audit_cannot_publish_action_or_authority() -> None:
    audit = manifest(str(service("AUD")["id"]))
    assert not {"BUS-ACT", "BUS-AUT", "BUS-STP"} & set(audit["outbound_buses"])
