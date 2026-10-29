"""Small dependency-free Python client for the FluxQueue HTTP API."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class FluxQueueError(RuntimeError):
    """API, network, or response error raised by FluxQueueClient."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FluxQueueClient:
    """Synchronous JSON client.

    Example:
        client = FluxQueueClient("http://127.0.0.1:8000", api_key="dev-key")
        job = client.submit({"task_type": "echo", "payload": {"message": "hello"}})
    """

    def __init__(self, base_url: str, api_key: str, *, timeout: float = 10.0) -> None:
        if not base_url.strip():
            raise ValueError("base_url must not be empty")
        if not api_key.strip():
            raise ValueError("api_key must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        parsed_url = urlsplit(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if (
            parsed_url.username
            or parsed_url.password
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("base_url must not contain credentials, query, or fragment")
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed_url.scheme != "https" and parsed_url.hostname not in local_hosts:
            raise ValueError("HTTPS is required when connecting to a non-local host")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: str = "",
        idempotency_key: str | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise FluxQueueError(
                f"FluxQueue API returned HTTP {exc.code}: {detail}",
                status_code=exc.code,
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise FluxQueueError(f"Unable to reach FluxQueue API: {exc}") from exc
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise FluxQueueError("FluxQueue API returned invalid JSON") from exc

    def submit(
        self, job: dict[str, Any], *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        """Submit a job and return the API response."""
        return self._request(
            "POST", "/api/v1/jobs", body=job, idempotency_key=idempotency_key
        )

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Fetch a job by ID."""
        return self._request("GET", f"/api/v1/jobs/{quote(job_id, safe='')}")

    def list_jobs(
        self,
        *,
        status: str | None = None,
        queue: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List jobs with optional filters and pagination."""
        from urllib.parse import urlencode

        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if queue:
            params["queue"] = queue
        return self._request("GET", "/api/v1/jobs", query=urlencode(params))

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a queued job."""
        path = f"/api/v1/jobs/{quote(job_id, safe='')}/cancel"
        return self._request("POST", path)

    def list_queues(self) -> dict[str, Any]:
        """Return queue counts available to this API key's tenant."""
        return self._request("GET", "/api/v1/queues")
