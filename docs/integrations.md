# Developer Tooling and Integrations

This repository keeps routine verification in GitHub Actions so contributors do not need to collect screenshots or manually copy test results.

## GitHub Actions

On pushes and pull requests, CI runs lint/format checks, migration validation, unit/API tests, container build and smoke checks, PostgreSQL locking tests, dependency auditing, and CodeQL. A weekly scheduled run catches drift even when there are no code changes.

JUnit test results and coverage XML are uploaded as workflow artifacts when available. Open the workflow run to inspect the machine-readable reports; screenshots are not part of the verification process.

## Codecov

The repository includes `.codecov.yml` and generates `coverage.xml` in GitHub Actions. The workflow uses the official Codecov Action and authenticates with the repository Actions secret `CODECOV_TOKEN`.

The upload was verified in GitHub Actions run [40882641655](https://github.com/vankudothuadhinaik/FluxQueue/actions/runs/40882641655): Codecov found `coverage.xml`, accepted the 3.6 KB upload, and reported **“Upload queued for processing complete.”** The report is queued for processing and can be viewed at the [Codecov commit report](https://app.codecov.io/github/vankudothuadhinaik/fluxqueue/commit/f5f6d93ee5212900ead0cfd9a79aa100d2ac91c5).

Keep the token only in GitHub Actions secrets; never commit it or paste it into source files, issues, or chat. Because the token appeared in a screenshot shared during setup, rotate/regenerate it in Codecov and replace the `CODECOV_TOKEN` repository secret with the new value. Then rerun CI to verify the rotated token works. Official guidance: https://github.com/codecov/codecov-action

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
- Codecov: coverage upload accepted and queued for processing in run [40882641655](https://github.com/vankudothuadhinaik/FluxQueue/actions/runs/40882641655); rotate the token exposed in the setup screenshot, update `CODECOV_TOKEN`, and rerun CI.
- Doppler: repository mapping ready; requires a matching Doppler project/config and authenticated CLI or deployment service token.
- CodeScene: requires the repository to be connected and analyzed in the CodeScene workspace.
- Render/other deployment: no production service is created by these files. Deploying a public service requires a deliberate environment, database, and cost decision.
