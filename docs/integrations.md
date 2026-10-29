# Developer Tooling and Integrations

This repository keeps routine verification in GitHub Actions so contributors do not need to collect screenshots or manually copy test results.

## GitHub Actions

On pushes and pull requests, CI runs lint/format checks, migration validation, unit/API tests, container build and smoke checks, PostgreSQL locking tests, dependency auditing, and CodeQL. A weekly scheduled run catches drift even when there are no code changes.

JUnit test results and coverage XML are uploaded as workflow artifacts when available. Open the workflow run to inspect the machine-readable reports; screenshots are not part of the verification process.

## Codecov

The repository includes `.codecov.yml` and generates `coverage.xml` in GitHub Actions. The workflow uses the official Codecov Action with GitHub OIDC (`use_oidc: true`) and grants the test job only the `id-token: write` permission needed for that authentication flow. This avoids storing a long-lived `CODECOV_TOKEN` secret in GitHub.

The latest upload attempt successfully obtained an OIDC token and verified the Codecov uploader, but Codecov rejected the upload with `Repository not found`. This means the upload pipeline is wired, but the repository still needs to be enabled/connected in the Codecov account and the Codecov GitHub App must have access to this private repository. Open the [FluxQueue Codecov project](https://app.codecov.io/gh/vankudothuadhinaik/FluxQueue) while signed in with the GitHub account that owns the repository, and complete repository setup / GitHub App access if prompted. Then rerun the latest workflow to verify that coverage is accepted.

The upload remains non-blocking until Codecov confirms the repository is configured. Never commit a Codecov token or put credentials in source files. Official guidance: https://github.com/codecov/codecov-action#using-oidc

## Doppler

The root `doppler.yaml` maps this repository to the Doppler project `fluxqueue`, config `dev`. The project and config must exist in the Doppler workspace; the mapping does not create them or contain secrets.

After installing and authenticating the Doppler CLI, use the repository directory and run:

```bash
doppler setup --no-interactive
doppler run -- docker compose up --build
```

The selected config should provide the non-secret configuration and secrets expected by Compose, especially `POSTGRES_PASSWORD` and `API_KEYS`. For production, use a separate production config and set `API_KEYS` to a JSON object mapping high-entropy bearer keys to tenant IDs; `API_KEY` is single-tenant compatibility only and is ignored when `API_KEYS` is non-empty. Do not add Doppler service tokens to the repository or CI logs. Official CLI guide: https://docs.doppler.com/docs/cli

## CodeScene

CodeScene analysis is managed by the CodeScene GitHub integration and workspace settings, not by a repository token committed to source control. Once the private repository is connected in CodeScene, use its pull-request/code-health findings alongside CI and CodeQL. This repository does not claim CodeScene analysis is active until the service reports a successful analysis.

## Copilot and Codex

Copilot and Codex are development assistants, not runtime dependencies. Keep their changes subject to the same tests, linting, migration checks, security analysis, and review gates as any other contribution. Never place production credentials in prompts or generated files.

## Current integration status

- GitHub Actions workflows and report artifacts: configured in source.
- CodeQL: configured in the CI workflow; result must be checked on the actual run.
- Python dependency audit: configured in the CI workflow; result must be checked on the actual run.
- Codecov: uploader/configuration ready; requires the repository's `CODECOV_TOKEN` secret to publish coverage.
- Doppler: repository mapping ready; requires a matching Doppler project/config and authenticated CLI or deployment service token.
- CodeScene: requires the repository to be connected and analyzed in the CodeScene workspace.
- Render/other deployment: no production service is created by these files. Deploying a public service requires a deliberate environment, database, and cost decision.
