"""Validate secret-manager-to-Compose wiring without printing secret values."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOPPLER_MAPPING = ("project: fluxqueue", "config: dev")
SERVICE_ENVIRONMENT = {
    "api": {
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
        "APP_ENV",
        "API_KEY",
        "API_KEYS",
        "MAX_ACTIVE_JOBS_PER_TENANT",
    },
    "worker": {
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
        "APP_ENV",
        "API_KEY",
        "API_KEYS",
        "MAX_ACTIVE_JOBS_PER_TENANT",
    },
    "db": {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"},
}


def fail(message: str) -> int:
    """Emit a safe diagnostic and return a failing exit code."""
    print(f"Doppler/Compose configuration error: {message}", file=sys.stderr)
    return 1


def parse_args() -> argparse.Namespace:
    """Parse the supported validation options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-doppler-env",
        action="store_true",
        help="require the non-empty POSTGRES_PASSWORD environment variable",
    )
    return parser.parse_args()


def validate_doppler_environment(required: bool) -> int:
    """Check required secret injection without revealing the secret."""
    if required and not os.environ.get("POSTGRES_PASSWORD"):
        return fail(
            "POSTGRES_PASSWORD was not injected; authenticate Doppler and check config dev"
        )
    return 0


def validate_project_mapping() -> int:
    """Ensure the repository mapping points at the expected Doppler config."""
    config_path = ROOT / "doppler.yaml"
    config = config_path.read_text(encoding="utf-8")
    if any(entry not in config for entry in REQUIRED_DOPPLER_MAPPING):
        return fail("doppler.yaml must reference project fluxqueue and config dev")
    return 0


def load_compose_configuration() -> dict[str, Any] | None:
    """Resolve Compose configuration while keeping its potentially secret output private."""
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        fail("docker compose config failed; check Compose syntax and variable names")
        return None
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError:
        fail("docker compose returned invalid configuration data")
        return None
    if not isinstance(document, dict):
        fail("docker compose returned an unexpected configuration shape")
        return None
    return document


def validate_service_environment(document: dict[str, Any]) -> int:
    """Check that API, worker, and database services declare required variables."""
    services = document.get("services", {})
    for service, required in SERVICE_ENVIRONMENT.items():
        definition = services.get(service, {})
        environment = definition.get("environment", {}) if isinstance(definition, dict) else {}
        present = set(environment) if isinstance(environment, dict) else set()
        missing = sorted(required - present)
        if missing:
            return fail(
                f"service {service} is missing environment mappings: {', '.join(missing)}"
            )
    return 0


def main() -> int:
    """Run the independent validation stages."""
    args = parse_args()
    if validate_doppler_environment(args.require_doppler_env):
        return 1
    if validate_project_mapping():
        return 1
    document = load_compose_configuration()
    if document is None:
        return 1
    if validate_service_environment(document):
        return 1
    print(
        "Doppler/Compose configuration is valid; required mappings are present for "
        "api, worker, and db."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
