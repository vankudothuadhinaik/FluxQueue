## Summary

<!-- Describe the behavior change and why it is needed. -->

## Verification

- [ ] Tests added or updated for behavior changes.
- [ ] `ruff check .` passes.
- [ ] `ruff format --check .` passes.
- [ ] Unit/API tests pass.
- [ ] PostgreSQL integration behavior is covered when relevant.
- [ ] Migration upgrade/downgrade behavior is checked when schema changes.
- [ ] CI container smoke checks and security jobs pass.

## Reliability and security

- [ ] No secrets or personal data are committed.
- [ ] Authentication and tenant boundaries are preserved.
- [ ] Retry/idempotency behavior is safe for side effects.
- [ ] Logs and error messages do not disclose credentials or sensitive payloads.
- [ ] Documentation and deployment gates are updated.

## Evidence

Link the relevant GitHub Actions run or machine-readable report artifact. Do not use screenshots as a substitute for CI results.
