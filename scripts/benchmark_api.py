#!/usr/bin/env python3
"""Repeatable API enqueue benchmark; run only against an environment you own."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round((percent / 100) * (len(ordered) - 1))))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--api-key",
        default=os.environ.get("FLUXQUEUE_API_KEY", ""),
        help="Bearer key; prefer FLUXQUEUE_API_KEY environment variable",
    )
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.timeout <= 0:
        parser.error("requests and concurrency must be positive; timeout must be positive")

    base_url = args.base_url.rstrip("/")
    latencies: list[float] = []
    statuses: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    started = time.perf_counter()

    def send_one(index: int) -> tuple[float, str, str | None]:
        body = json.dumps(
            {
                "task_type": "echo",
                "payload": {"benchmark_run": str(uuid4()), "sequence": index},
                "queue": "benchmark",
                "priority": 5,
                "max_attempts": 1,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": f"fluxqueue-benchmark-{uuid4()}",
        }
        if args.api_key:
            headers["Authorization"] = f"Bearer {args.api_key}"
        request = Request(f"{base_url}/api/v1/jobs", data=body, headers=headers, method="POST")
        before = time.perf_counter()
        try:
            with urlopen(request, timeout=args.timeout) as response:
                response.read()
                return time.perf_counter() - before, str(response.status), None
        except HTTPError as exc:
            exc.read()
            return time.perf_counter() - before, str(exc.code), f"HTTP {exc.code}"
        except (TimeoutError, URLError, OSError) as exc:
            return time.perf_counter() - before, "transport_error", type(exc).__name__

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(send_one, index) for index in range(args.requests)]
        for future in as_completed(futures):
            latency, status, error = future.result()
            latencies.append(latency)
            statuses[status] += 1
            if error:
                errors[error] += 1

    elapsed = time.perf_counter() - started
    print(f"target: {base_url}/api/v1/jobs")
    print(f"requests: {args.requests}; concurrency: {args.concurrency}; elapsed: {elapsed:.3f}s")
    print(f"throughput: {args.requests / elapsed:.2f} requests/s")
    print(
        "latency ms: "
        f"mean={statistics.fmean(latencies) * 1000:.2f}, "
        f"p50={percentile(latencies, 50) * 1000:.2f}, "
        f"p95={percentile(latencies, 95) * 1000:.2f}, "
        f"p99={percentile(latencies, 99) * 1000:.2f}"
    )
    print(f"status counts: {dict(sorted(statuses.items()))}")
    if errors:
        print(f"transport/HTTP errors: {dict(sorted(errors.items()))}")
    success = statuses.get("202", 0)
    return 0 if success == args.requests else 1



if __name__ == "__main__":
    raise SystemExit(main())
