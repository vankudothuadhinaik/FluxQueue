# Security Policy

Report vulnerabilities privately to the repository owner; do not publish exploitable details in public issues.

## Current security boundaries

- This is an early-stage API; do not expose it to the public internet.
- A shared bearer API key is supported for protected job/queue routes. Tenant-level authorization and per-user identities are not implemented. Production configuration requires `API_KEY`.
- Never accept shell commands, import paths, or executable code as job payloads.
- The API limits serialized job payloads to 64 KiB; also enforce request-body limits at the proxy/edge.
- Never commit credentials, tokens, local environment files, or database files.
- The Docker image runs as a non-root UID; retain that restriction in deployment overrides.
- Replace local-only database passwords before shared use.
- Keep operational endpoints behind authentication when they are added.

## Production gate

Before public deployment, implement and test authentication, authorization, request and payload limits, rate limiting, dependency scanning, secret management, safe error redaction, and restricted operator actions. A CodeQL workflow alone is not proof of security.
