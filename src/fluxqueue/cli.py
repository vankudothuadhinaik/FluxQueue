"""Command-line interface for FluxQueue; invoke with `python -m fluxqueue.cli`."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from fluxqueue.sdk import FluxQueueClient, FluxQueueError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit and inspect FluxQueue jobs.")
    parser.add_argument(
        "--base-url", default=os.getenv("FLUXQUEUE_URL", "http://127.0.0.1:8000"),
        help="API base URL (default: FLUXQUEUE_URL or localhost)",
    )
    parser.add_argument(
        "--api-key", default=os.getenv("FLUXQUEUE_API_KEY"),
        help="Bearer API key (default: FLUXQUEUE_API_KEY environment variable)",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    commands = parser.add_subparsers(dest="command", required=True)

    submit = commands.add_parser("submit", help="submit a job from JSON")
    source = submit.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", help="job JSON object")
    source.add_argument("--file", type=Path, help="path to a UTF-8 JSON file")
    submit.add_argument("--idempotency-key", help="optional idempotency key")

    get = commands.add_parser("get", help="fetch a job by ID")
    get.add_argument("job_id")

    listing = commands.add_parser("list", help="list jobs")
    listing.add_argument("--status", choices=[
        "queued", "running", "succeeded", "retry_wait", "dead", "cancelled"
    ])
    listing.add_argument("--queue")
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--offset", type=int, default=0)

    cancel = commands.add_parser("cancel", help="cancel a queued job")
    cancel.add_argument("job_id")
    commands.add_parser("queues", help="show queue counts")
    return parser


def _load_job(args: argparse.Namespace) -> dict[str, Any]:
    raw = args.json if args.json is not None else args.file.read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("job JSON must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.api_key:
        parser.error("provide --api-key or set FLUXQUEUE_API_KEY")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    client = FluxQueueClient(args.base_url, args.api_key, timeout=args.timeout)
    try:
        if args.command == "submit":
            result = client.submit(_load_job(args), idempotency_key=args.idempotency_key)
        elif args.command == "get":
            result = client.get_job(args.job_id)
        elif args.command == "list":
            result = client.list_jobs(
                status=args.status, queue=args.queue, limit=args.limit, offset=args.offset
            )
        elif args.command == "cancel":
            result = client.cancel_job(args.job_id)
        else:
            result = client.list_queues()
    except (FluxQueueError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fluxqueue: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
