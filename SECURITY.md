# Security Policy

Report vulnerabilities privately to the repository owner; do not publish exploitable details in public issues.

## Current security boundaries

- This is an early-stage API; do not expose it to the public internet.
- Authentication and tenant authorization are not implemented.
- Never accept shell commands, import paths, or executable code as job payloads.
- Never commit credentials, tokens, local environment files, or database files.
- Replace local-only database passwords before shared use.
- Keep operational endpoints behind authentication when they are added.

## Production gate

Before public deployment, implement and test authentication, authorization, request and payload limits, rate limiting, dependency scanning, secret management, safe error redaction, and restricted operator actions. A CodeQL workflow alone is not proof of security.
