"""Validate secret-manager-to-Compose wiring without printing secret values."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

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
    print(f"Doppler/Compose configuration error: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-doppler-env",
        action="store_true",
        help="require the non-empty POSTGRES_PASSWORD environment variable",
    )
    args = parser.parse_args()

    if args.require_doppler_env and not os.environ.get("POSTGRES_PASSWORD"):
        return fail("POSTGRES_PASSWORD was not injected; authenticate Doppler and check config dev")

    doppler_config = (ROOT / "doppler.yaml").read_text(encoding="utf-8")
    missing_mapping = [entry for entry in REQUIRED_DOPPLER_MAPPING if entry not in doppler_config]
    if missing_mapping:
        return fail("doppler.yaml must reference project fluxqueue and config dev")

    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return fail("docker compose config failed; check Compose syntax and variable names")

    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError:
        return fail("docker compose returned invalid configuration data")

    services = document.get("services", {})
    for service, required in SERVICE_ENVIRONMENT.items():
        environment = services.get(service, {}).get("environment", {})
        present = set(environment) if isinstance(environment, dict) else set()
        missing = sorted(required - present)
        if missing:
            return fail(f"service {service} is missing environment mappings: {', '.join(missing)}")

    print(
        "Doppler/Compose configuration is valid; required mappings are present for "
        "api, worker, and db."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
