#!/usr/bin/env python3
"""Interroga procesos vivos y compara sus proveedores con los manifiestos."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def fetch(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")  # noqa: S310 -- operador elige host
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise ValueError(f"malformed object returned by {url}")
    return payload


def fetch_via_compose(url: str, timeout: float) -> dict[str, Any]:
    """Fetch through the isolated service network without publishing host ports."""
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        raise OSError("docker executable not found")
    program = (
        "import sys, urllib.request; "
        "sys.stdout.write(urllib.request.urlopen(sys.argv[1], timeout=float(sys.argv[2]))"
        ".read().decode('utf-8'))"
    )
    result = subprocess.run(  # noqa: S603 -- fixed executable and arguments
        [
            docker_executable,
            "compose",
            "-f",
            str(ROOT / "deploy/local/docker-compose.yml"),
            "exec",
            "-T",
            "experience-service",
            "python",
            "-c",
            program,
            url,
            str(timeout),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout + 5.0,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "compose request failed"
        raise OSError(detail)
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise ValueError(f"malformed object returned by {url}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--services", nargs="*", default=[])
    parser.add_argument("--allow-unavailable", action="store_true")
    parser.add_argument(
        "--via-compose",
        action="store_true",
        help="probe service DNS from the isolated Compose network",
    )
    args = parser.parse_args()

    registry = yaml.safe_load((ROOT / "registry/services.yaml").read_text(encoding="utf-8"))
    selected = set(args.services)
    services: list[dict[str, Any]] = []
    errors: list[str] = []
    active_modules: set[str] = set()
    declared_modules: set[str] = set()

    for registered in registry["services"]:
        service_id = registered["id"]
        if selected and service_id not in selected:
            continue
        manifest_path = ROOT / "services" / service_id / "service.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if args.via_compose:
            base_url = f"http://{service_id}:8080"
            fetch_runtime = fetch_via_compose
        else:
            base_url = f"http://{args.host}:{registered['port']}"
            fetch_runtime = fetch
        expected_providers = {item["id"]: item for item in manifest.get("providers", [])}
        declared_modules.update(manifest["modules"])
        try:
            readiness = fetch_runtime(f"{base_url}{manifest['health']['readiness']}", args.timeout)
            runtime = fetch_runtime(f"{base_url}/v1/modules", args.timeout)
        except (
            OSError,
            ValueError,
            subprocess.TimeoutExpired,
            urllib.error.URLError,
        ) as exc:
            services.append({"service": service_id, "status": "unavailable", "error": str(exc)})
            if not args.allow_unavailable:
                errors.append(f"{service_id} unavailable: {exc}")
            continue

        actual_providers = {item["id"]: item for item in runtime.get("providers", [])}
        expected_ids = set(expected_providers)
        actual_ids = set(actual_providers)
        if expected_ids != actual_ids:
            errors.append(
                f"{service_id} provider mismatch: expected {sorted(expected_ids)}, "
                f"got {sorted(actual_ids)}"
            )
        if set(runtime.get("declared_modules", [])) != set(manifest["modules"]):
            errors.append(f"{service_id} runtime declaration differs from service manifest")
        for provider_id, expected in expected_providers.items():
            actual = actual_providers.get(provider_id)
            if actual is None:
                continue
            if set(actual.get("modules", [])) != set(expected["modules"]):
                errors.append(f"{service_id}/{provider_id} module binding differs")
            if actual.get("endpoint") != expected["endpoint"]:
                errors.append(f"{service_id}/{provider_id} endpoint binding differs")
            if set(actual.get("methods", [])) != set(expected["methods"]):
                errors.append(f"{service_id}/{provider_id} method binding differs")
            if not all(
                [
                    actual.get("status") == "loaded",
                    actual.get("route_bound") is True,
                    actual.get("invocable") is True,
                ]
            ):
                errors.append(f"{service_id}/{provider_id} is not a loaded invocable route")

        provided = set(runtime.get("provided_modules", []))
        active_modules.update(provided)
        services.append(
            {
                "service": service_id,
                "status": "ready",
                "readiness": readiness,
                "declared": len(runtime.get("declared_modules", [])),
                "provided": len(provided),
                "provided_modules": sorted(provided),
                "unprovided_modules": sorted(runtime.get("unprovided_modules", [])),
            }
        )

    output = {
        "services": services,
        "summary": {
            "services_probed": len(services),
            "services_ready": sum(item["status"] == "ready" for item in services),
            "declared_modules_in_selected_services": len(declared_modules),
            "runtime_modules_with_loaded_providers": len(active_modules),
            "loaded_module_ids": sorted(active_modules),
            "errors": errors,
        },
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
