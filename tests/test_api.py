"""API contract and lifecycle tests."""

import pytest


def submit(client, payload=None, headers=None):
    body = {
        "task_type": "echo",
        "payload": {"message": "hello"},
        "queue": "default",
        "priority": 5,
        "max_attempts": 3,
    }
    if payload:
        body.update(payload)
    response = client.post("/api/v1/jobs", json=body, headers=headers or {})
    assert response.status_code == 202, response.text
    return response.json()


def test_health_and_readiness(client):
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").status_code == 200


def test_submit_and_retrieve(client):
    job = submit(client)
    result = client.get(f"/api/v1/jobs/{job['id']}")
    assert result.status_code == 200
    assert result.json()["status"] == "queued"
    assert result.json()["payload"]["message"] == "hello"


def test_list_filter_and_pagination(client):
    submit(client, {"queue": "mail"})
    submit(client, {"queue": "reports"})
    result = client.get("/api/v1/jobs?queue=mail&limit=1")
    assert result.status_code == 200
    assert result.json()["total"] == 1
    assert len(result.json()["items"]) == 1


def test_idempotent_submission_returns_same_job(client):
    headers = {"Idempotency-Key": "request-1"}
    first = submit(client, headers=headers)
    second = submit(client, headers=headers)
    assert first["id"] == second["id"]


def test_reusing_idempotency_key_with_different_payload_conflicts(client):
    headers = {"Idempotency-Key": "request-1"}
    submit(client, headers=headers)
    response = client.post(
        "/api/v1/jobs",
        json={"task_type": "echo", "payload": {"different": True}},
        headers=headers,
    )
    assert response.status_code == 409


def test_cancel_queued_job(client):
    job = submit(client)
    result = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert result.status_code == 200
    assert result.json()["status"] == "cancelled"


def test_cannot_cancel_terminal_job_twice(client):
    job = submit(client)
    client.post(f"/api/v1/jobs/{job['id']}/cancel")
    result = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert result.status_code == 409


def test_missing_job_is_404(client):
    assert client.get("/api/v1/jobs/no-such-id").status_code == 404


def test_invalid_priority_is_rejected(client):
    response = client.post("/api/v1/jobs", json={"task_type": "echo", "priority": 99})
    assert response.status_code == 422


def test_invalid_status_filter_is_rejected(client):
    assert client.get("/api/v1/jobs?status=not-a-state").status_code == 422


def test_configured_api_key_protects_all_api_route_families(client, monkeypatch):
    from fluxqueue.auth import settings

    monkeypatch.setattr(settings, "api_key", "test-secret")
    protected_requests = [
        ("GET", "/api/v1/jobs"),
        ("POST", "/api/v1/jobs"),
        ("GET", "/api/v1/jobs/missing-job"),
        ("POST", "/api/v1/jobs/missing-job/cancel"),
        ("GET", "/api/v1/queues"),
    ]
    for method, path in protected_requests:
        kwargs = (
            {"json": {"task_type": "echo", "payload": {}}}
            if path == "/api/v1/jobs" and method == "POST"
            else {}
        )
        response = client.request(method, path, **kwargs)
        assert response.status_code == 401, f"{method} {path}: {response.status_code}"

    assert client.get("/api/v1/jobs", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert (
        client.get("/api/v1/jobs", headers={"Authorization": "Basic test-secret"}).status_code
        == 401
    )
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200

    response = client.get("/api/v1/jobs", headers={"Authorization": "Bearer test-secret"})
    assert response.status_code == 200


def test_production_settings_require_api_key():
    from pydantic import ValidationError

    from fluxqueue.config import Settings

    with pytest.raises(ValidationError):
        Settings(app_env="production", api_key=None)


def test_oversized_payload_is_rejected(client):
    response = client.post(
        "/api/v1/jobs",
        json={"task_type": "echo", "payload": {"data": "x" * 65_537}},
    )
    assert response.status_code == 422


def test_delayed_job_persists_run_time(client):
    response = client.post(
        "/api/v1/jobs",
        json={"task_type": "echo", "payload": {}, "delay_seconds": 60},
    )
    assert response.status_code == 202
    assert response.json()["run_at"] is not None


def test_non_finite_numbers_are_rejected_in_payload(client):
    response = client.post(
        "/api/v1/jobs",
        content='{"task_type":"echo","payload":{"not_finite":NaN}}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422


def test_delay_is_bounded(client):
    response = client.post(
        "/api/v1/jobs",
        json={"task_type": "echo", "payload": {}, "delay_seconds": 86_401},
    )
    assert response.status_code == 422


def test_idempotency_keys_are_scoped_to_queue(client):
    headers = {"Idempotency-Key": "shared-key"}
    first = submit(client, {"queue": "mail"}, headers=headers)
    second = submit(client, {"queue": "reports"}, headers=headers)
    assert first["id"] != second["id"]
