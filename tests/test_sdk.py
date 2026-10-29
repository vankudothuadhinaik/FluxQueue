"""SDK and CLI contract tests without a live API server."""

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from fluxqueue import sdk
from fluxqueue.cli import main
from fluxqueue.sdk import FluxQueueClient, FluxQueueError


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def test_sdk_submit_sends_bearer_and_idempotency_headers(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeResponse({"id": "job-1", "status": "queued"})

    monkeypatch.setattr(sdk, "urlopen", fake_urlopen)
    client = FluxQueueClient("http://localhost:8000/", "test-key", timeout=2)
    result = client.submit(
        {"task_type": "echo", "payload": {"message": "hi"}},
        idempotency_key="once-only",
    )

    assert result["id"] == "job-1"
    assert captured["url"] == "http://localhost:8000/api/v1/jobs"
    assert captured["method"] == "POST"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["Idempotency-key"] == "once-only"
    assert captured["body"]["task_type"] == "echo"
    assert captured["timeout"] == 2


def test_sdk_list_encodes_query_parameters(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse({"items": [], "total": 0})

    monkeypatch.setattr(sdk, "urlopen", fake_urlopen)
    result = FluxQueueClient("http://localhost", "key").list_jobs(
        status="retry_wait", queue="mail queue", limit=10, offset=20
    )
    assert result["total"] == 0
    assert "status=retry_wait" in captured["url"]
    assert "queue=mail+queue" in captured["url"]
    assert "limit=10" in captured["url"]


def test_sdk_surfaces_http_status_and_body(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url, 404, "missing", {}, BytesIO(b'{"detail":"not found"}')
        )

    monkeypatch.setattr(sdk, "urlopen", fake_urlopen)
    with pytest.raises(FluxQueueError, match="HTTP 404") as exc:
        FluxQueueClient("http://localhost", "key").get_job("missing")
    assert exc.value.status_code == 404
    assert "not found" in str(exc.value)


def test_cli_submit_prints_json(monkeypatch, capsys):
    from fluxqueue import cli

    monkeypatch.setattr(cli, "_load_job", lambda args: {
        "task_type": "echo", "payload": {"message": "hello"}
    })

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def submit(self, job, *, idempotency_key=None):
            return {"id": "job-2", "status": "queued"}

    monkeypatch.setattr(cli, "FluxQueueClient", FakeClient)
    assert (
        main(["--api-key", "key", "submit", "--json", '{"task_type":"echo","payload":{}}'])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["id"] == "job-2"


def test_cli_reports_missing_api_key():
    with pytest.raises(SystemExit) as exc:
        main(["list"])
    assert exc.value.code == 2



def test_sdk_rejects_invalid_constructor_settings():
    with pytest.raises(ValueError, match="base_url"):
        FluxQueueClient("", "key")
    with pytest.raises(ValueError, match="api_key"):
        FluxQueueClient("http://localhost", " ")
    with pytest.raises(ValueError, match="timeout"):
        FluxQueueClient("http://localhost", "key", timeout=0)


def test_sdk_encodes_job_identifier_as_one_path_segment(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse({"id": "safe"})

    monkeypatch.setattr(sdk, "urlopen", fake_urlopen)
    FluxQueueClient("http://localhost", "key").get_job("../admin?x=1")
    assert captured["url"] == "http://localhost/api/v1/jobs/..%2Fadmin%3Fx%3D1"


def test_sdk_rejects_non_json_success_response(monkeypatch):
    class InvalidResponse(FakeResponse):
        def __init__(self):
            self.payload = b"not-json"

    monkeypatch.setattr(sdk, "urlopen", lambda request, timeout: InvalidResponse())
    with pytest.raises(FluxQueueError, match="invalid JSON"):
        FluxQueueClient("http://localhost", "key").get_job("job-1")


def test_sdk_wraps_network_errors(monkeypatch):
    from urllib.error import URLError

    def fail_urlopen(request, timeout):
        raise URLError("offline")

    monkeypatch.setattr(sdk, "urlopen", fail_urlopen)
    with pytest.raises(FluxQueueError, match="Unable to reach"):
        FluxQueueClient("http://localhost", "key").get_job("job-1")



def test_sdk_requires_https_for_non_local_hosts():
    with pytest.raises(ValueError, match="HTTPS is required"):
        FluxQueueClient("http://api.example.com", "secret")
    assert FluxQueueClient("https://api.example.com", "secret")
    assert FluxQueueClient("http://127.0.0.1:8000", "local-key")


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://localhost",
        "/relative/path",
        "https://user:password@example.com",
        "https://example.com/path?token=secret",
        "https://example.com/#fragment",
    ],
)
def test_sdk_rejects_unsafe_or_invalid_base_urls(base_url):
    with pytest.raises(ValueError):
        FluxQueueClient(base_url, "secret")
