# Developer Tooling and Integrations

This repository keeps routine verification in GitHub Actions so contributors do not need to collect screenshots or manually copy test results.

## GitHub Actions

On pushes and pull requests, CI runs lint/format checks, migration validation, unit/API tests, container build and smoke checks, PostgreSQL locking tests, dependency auditing, and CodeQL. A weekly scheduled run catches drift even when there are no code changes.

JUnit test results and coverage XML are uploaded as workflow artifacts when available. Open the workflow run to inspect the machine-readable reports; screenshots are not part of the verification process.

## Codecov

The repository includes `.codecov.yml`. CI uploads `coverage.xml` only when the GitHub Actions repository secret `CODECOV_TOKEN` exists. Without the secret, the upload step is skipped and CI still runs normally.

Set the secret once in the repository's Actions secrets, using the token from the FluxQueue Codecov project. Never commit the token or paste it into source files. Official guidance: https://docs.codecov.com/docs/codecov-tokens

## Doppler

The root `doppler.yaml` maps this repository to the Doppler project `fluxqueue`, config `dev`. The project and config must exist in the Doppler workspace; the mapping does not create them or contain secrets.

After installing and authenticating the Doppler CLI, use the repository directory and run:

```bash
doppler setup --no-interactive
doppler run -- docker compose up --build
```

The selected config should provide the non-secret configuration and secrets expected by Compose, especially `POSTGRES_PASSWORD` and `API_KEY`. For production, use a separate production config and a high-entropy API key. Do not add Doppler service tokens to the repository or CI logs. Official CLI guide: https://docs.doppler.com/docs/cli

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
