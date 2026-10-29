# Security Policy

Report vulnerabilities privately to the repository owner; do not publish exploitable details in public issues.

## Current security boundaries

- This is an early-stage API; do not expose it to the public internet.
- Protected job/queue routes derive tenant identity from the authenticated bearer key. Configure `API_KEYS` as a JSON mapping from high-entropy API keys to tenant identifiers; the legacy `API_KEY` maps all callers to the `default` tenant and is for single-tenant use only. Production configuration requires `API_KEYS` or `API_KEY`; when `API_KEYS` is non-empty, it takes precedence and the legacy key is ignored.
- Never accept shell commands, import paths, or executable code as job payloads.
- The API limits serialized job payloads to 64 KiB; also enforce request-body limits at the proxy/edge.
- Never commit credentials, tokens, local environment files, or database files.
- The Docker image runs as a non-root UID; retain that restriction in deployment overrides.
- Replace local-only database passwords before shared use.
- Every job lookup, listing, cancellation, queue aggregate, and idempotency lookup must include the authenticated tenant scope.
- Tenant API keys are shared secrets; there are no individual user identities, key-expiry metadata, or self-service rotation endpoints yet.
- Keep operational endpoints behind authentication when they are added.

## Production gate

Before public deployment, verify tenant authorization tests in CI, add and test rate limiting and per-tenant quotas, review request/payload limits, dependency scanning, secret rotation, safe error redaction, and restricted operator actions. A CodeQL workflow alone is not proof of security.
