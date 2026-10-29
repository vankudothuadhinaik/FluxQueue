"""API contract and lifecycle tests."""


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
