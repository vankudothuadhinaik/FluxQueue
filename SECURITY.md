# Security Policy

Report vulnerabilities privately to the repository owner; do not publish exploit details in issues.

## Current boundaries

- Do not expose the early-stage API to the public internet.
- Authentication and tenant authorization are not implemented yet.
- Never accept shell commands, import paths, or executable code from job payloads.
- Do not commit credentials or local .env files.
- Replace local-only database passwords before any shared deployment.
- Production requires authentication, authorization, rate and size limits, dependency scanning, and controlled operational actions.
