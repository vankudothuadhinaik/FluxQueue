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


def test_tenants_cannot_read_cancel_or_list_each_others_jobs(client, monkeypatch):
    from fluxqueue.auth import settings

    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(
        settings,
        "api_keys",
        {"tenant-a-secret": "tenant-a", "tenant-b-secret": "tenant-b"},
    )
    tenant_a = {"Authorization": "Bearer tenant-a-secret", "Idempotency-Key": "shared-key"}
    tenant_b = {"Authorization": "Bearer tenant-b-secret", "Idempotency-Key": "shared-key"}

    first = client.post(
        "/api/v1/jobs",
        json={"task_type": "echo", "queue": "mail", "payload": {"tenant": "a"}},
        headers=tenant_a,
    )
    second = client.post(
        "/api/v1/jobs",
        json={"task_type": "echo", "queue": "mail", "payload": {"tenant": "b"}},
        headers=tenant_b,
    )
    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    first_job = first.json()
    second_job = second.json()
    assert first_job["id"] != second_job["id"]

    assert (
        client.get("/api/v1/jobs", headers={"Authorization": "Bearer invalid-secret"}).status_code
        == 401
    )
    tenant_a_jobs = client.get("/api/v1/jobs", headers=tenant_a)
    tenant_b_jobs = client.get("/api/v1/jobs", headers=tenant_b)
    assert tenant_a_jobs.status_code == 200
    assert tenant_b_jobs.status_code == 200
    assert [job["id"] for job in tenant_a_jobs.json()["items"]] == [first_job["id"]]
    assert [job["id"] for job in tenant_b_jobs.json()["items"]] == [second_job["id"]]

    assert client.get(f"/api/v1/jobs/{first_job['id']}", headers=tenant_b).status_code == 404
    assert (
        client.post(f"/api/v1/jobs/{first_job['id']}/cancel", headers=tenant_b).status_code
        == 404
    )
    assert client.get("/api/v1/queues", headers=tenant_b).json() == [
        {"name": "mail", "counts": {"queued": 1}}
    ]
    assert (
        client.get(f"/api/v1/jobs/{first_job['id']}", headers=tenant_a).json()["status"]
        == "queued"
    )


def test_production_settings_accept_tenant_api_keys():
    from fluxqueue.config import Settings

    configured = Settings(
        app_env="production",
        api_key=None,
        api_keys={"tenant-a-secret": "tenant-a"},
    )
    assert configured.api_keys == {"tenant-a-secret": "tenant-a"}


def test_client_cannot_choose_its_own_tenant(client, monkeypatch):
    from fluxqueue.auth import settings

    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "api_keys", {"tenant-b-secret": "tenant-b"})
    response = client.post(
        "/api/v1/jobs",
        json={
            "task_type": "echo",
            "payload": {"message": "hello"},
            "tenant_id": "tenant-a",
        },
        headers={"Authorization": "Bearer tenant-b-secret"},
    )
    assert response.status_code == 202, response.text
    jobs = client.get("/api/v1/jobs", headers={"Authorization": "Bearer tenant-b-secret"})
    assert jobs.status_code == 200
    assert [job["payload"]["message"] for job in jobs.json()["items"]] == ["hello"]



def test_tenant_key_mapping_takes_precedence_over_legacy_key(client, monkeypatch):
    from fluxqueue.auth import settings

    monkeypatch.setattr(settings, "api_key", "legacy-secret")
    monkeypatch.setattr(settings, "api_keys", {"tenant-secret": "tenant-a"})
    assert (
        client.get("/api/v1/jobs", headers={"Authorization": "Bearer legacy-secret"}).status_code
        == 401
    )
    assert (
        client.get("/api/v1/jobs", headers={"Authorization": "Bearer tenant-secret"}).status_code
        == 200
    )



def test_unicode_api_key_comparison_is_supported(monkeypatch):
    from fluxqueue.auth import require_api_key, settings

    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "api_keys", {"clé-secret": "tenant-a"})
    assert require_api_key("Bearer clé-secret") == "tenant-a"


def test_tenant_api_key_settings_reject_invalid_tenant_ids():
    from pydantic import ValidationError

    from fluxqueue.config import Settings

    with pytest.raises(ValidationError):
        Settings(app_env="production", api_keys={"valid-secret": ""})
    with pytest.raises(ValidationError):
        Settings(app_env="production", api_keys={"valid-secret": "x" * 129})


def test_security_headers_are_set_on_api_responses(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"


def test_active_job_quota_is_enforced_per_tenant(client, monkeypatch):
    from fluxqueue.auth import settings as auth_settings

    monkeypatch.setattr(auth_settings, "api_key", None)
    monkeypatch.setattr(
        auth_settings,
        "api_keys",
        {"tenant-a-secret": "tenant-a", "tenant-b-secret": "tenant-b"},
    )
    monkeypatch.setattr(auth_settings, "max_active_jobs_per_tenant", 1)

    tenant_a = {"Authorization": "Bearer tenant-a-secret"}
    tenant_b = {"Authorization": "Bearer tenant-b-secret"}
    first = client.post(
        "/api/v1/jobs",
        json={"task_type": "echo", "payload": {"n": 1}},
        headers=tenant_a,
    )
    assert first.status_code == 202
    rejected = client.post(
        "/api/v1/jobs",
        json={"task_type": "echo", "payload": {"n": 2}},
        headers=tenant_a,
    )
    assert rejected.status_code == 429
    accepted_for_other_tenant = client.post(
        "/api/v1/jobs",
        json={"task_type": "echo", "payload": {"n": 3}},
        headers=tenant_b,
    )
    assert accepted_for_other_tenant.status_code == 202


def test_idempotent_retry_is_allowed_when_tenant_quota_is_full(client, monkeypatch):
    from fluxqueue.auth import settings

    monkeypatch.setattr(settings, "max_active_jobs_per_tenant", 1)
    headers = {"Idempotency-Key": "quota-idempotency"}
    first = submit(client, headers=headers)
    duplicate = submit(client, headers=headers)
    assert duplicate["id"] == first["id"]
