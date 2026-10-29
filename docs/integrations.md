# Developer Tooling and Integrations

This repository keeps routine verification in GitHub Actions so contributors do not need to collect screenshots or manually copy test results.

## GitHub Actions

On pushes and pull requests, CI runs lint/format checks, migration validation, unit/API tests, container build and smoke checks, PostgreSQL locking tests, dependency auditing, and CodeQL. A weekly scheduled run catches drift even when there are no code changes.

JUnit test results and coverage XML are uploaded as workflow artifacts when available. Open the workflow run to inspect the machine-readable reports; screenshots are not part of the verification process.

## Codecov

The repository includes `.codecov.yml` and generates `coverage.xml` in GitHub Actions. The workflow uses the official Codecov Action and authenticates with the repository Actions secret `CODECOV_TOKEN`.

The upload was verified in GitHub Actions run [40882641655](https://github.com/vankudothuadhinaik/FluxQueue/actions/runs/40882641655): Codecov found `coverage.xml`, accepted the 3.6 KB upload, and reported **“Upload queued for processing complete.”** The report was queued for processing and can be viewed at the [Codecov commit report](https://app.codecov.io/github/vankudothuadhinaik/fluxqueue/commit/f5f6d93ee5212900ead0cfd9a79aa100d2ac91c5).

Keep the token only in GitHub Actions secrets; never commit it or paste it into source files, issues, or chat. Because the token appeared in a screenshot shared during setup, rotate/regenerate it in Codecov and replace the `CODECOV_TOKEN` repository secret with the new value. Then rerun CI to verify the rotated token works. Official guidance: https://github.com/codecov/codecov-action

The final PR check on commit `81b567b413a744044528af75d19d6772d19194aa` also passed Codecov's patch check: [Codecov patch check](https://github.com/vankudothuadhinaik/FluxQueue/runs/123521397956). This proves the upload/check succeeded, but does not prove that the exposed credential was rotated; that remains an account-owner action unless the replacement is separately verified.

## Doppler

The root `doppler.yaml` maps this repository to the Doppler project `fluxqueue`, config `dev`. The mapping is intentionally the same in every setup instruction. It is only a local CLI mapping; it does not create the project/config or prove the workspace is connected.

### One-time workspace setup

1. In the Doppler dashboard, create a project named `fluxqueue` and a config named `dev` (or adjust `doppler.yaml` to match your actual names).
2. Add these values to the `dev` config:
   - `POSTGRES_PASSWORD`: a non-empty local-development password, not the Compose fallback. Compose passes it separately and FluxQueue safely URL-encodes it when building the local database URL.
   - `APP_ENV`: `development` for this local stack.
   - `API_KEYS`: `{}` for local unauthenticated development, or a JSON object mapping high-entropy bearer keys to tenant IDs for authenticated testing.
   - `MAX_ACTIVE_JOBS_PER_TENANT`: `1000` (optional; this is the application default).
   - `DATABASE_URL`: optional. If omitted, FluxQueue builds the PostgreSQL URL from `POSTGRES_PASSWORD`; supplying it is useful when the database is not the Compose `db` service.
3. Do not paste Doppler service tokens into GitHub source files, issues, logs, or chat. Use the Doppler CLI login flow for a developer machine; use a narrowly scoped service token only in a secret store for automation/deployments. No Doppler token is required by this repository's CI workflow.

### Verify locally

Install the Doppler CLI and authenticate with `doppler login`. From the repository root, run:

```bash
doppler setup --no-interactive
doppler run -- python scripts/validate_doppler_config.py --require-doppler-env
doppler run -- docker compose config --quiet
doppler run -- docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:8000/health/ready
```

The validator checks the `fluxqueue`/`dev` mapping and confirms the required environment names are wired to API, worker, and PostgreSQL. With `--require-doppler-env`, it also requires a non-empty injected `POSTGRES_PASSWORD`. It never prints resolved environment values. Confirm the API readiness response and `docker compose ps` show healthy services. Stop the stack with `docker compose down` when finished. Never run `docker compose down -v` against a database whose data must be retained.

### Troubleshooting Doppler/Compose

- `POSTGRES_PASSWORD was not injected`: run `doppler login`, repeat `doppler setup --no-interactive`, and verify the selected project is `fluxqueue` and config is `dev`. Do not work around this by committing a token or password.
- `docker compose config failed`: run `docker compose config --quiet` without Doppler to isolate Compose syntax, then rerun through `doppler run`. Check that `API_KEYS` is valid JSON. If supplying `DATABASE_URL` directly, URL-encode its password component.
- API readiness fails while PostgreSQL is healthy: inspect `docker compose logs --no-log-prefix api` for non-secret error text and verify `DATABASE_URL` points at `db` when using the included PostgreSQL service. Never use `docker compose config` output as a log artifact because it contains resolved secrets.
- Worker is unhealthy or idle: check `docker compose logs --no-log-prefix worker`; the worker shares the API's resolved database/application environment and does not need a separate token.
- A changed Doppler value is not active: restart or recreate the services; settings are read at process startup.

### Production boundary

Create a separate production config; do not reuse `dev`. Set `APP_ENV=production`, a strong `POSTGRES_PASSWORD`, and `API_KEYS` as a JSON object mapping high-entropy bearer keys to tenant IDs. `API_KEY` is single-tenant compatibility only and is ignored when `API_KEYS` is non-empty. This Compose stack binds ports to loopback and is intended for local use; Doppler setup alone does not create a production deployment. Do not add Doppler service tokens to the repository or CI logs. Official CLI guide: https://docs.doppler.com/docs/cli

## CodeScene

CodeScene must be connected through its workspace and GitHub integration; do not add a CodeScene token or private key to this repository. For GitHub.com, use the official [CodeScene Access GitHub App](https://github.com/apps/codescene-access/installations/new) where possible. It is the current recommended app for repository access and pull-request checks.

### Connect and verify

1. Sign in to [CodeScene](https://codescene.io/) using the GitHub account that owns or can access `vankudothuadhinaik/FluxQueue`.
2. Install/authorize **CodeScene Access** for the FluxQueue repository. Grant access only to the repositories you intend CodeScene to analyze.
3. In CodeScene, create a project and select `vankudothuadhinaik/FluxQueue`; launch the initial analysis and wait for a successful result.
4. If pull-request checks are desired, open the project's **Pull Request Integration** settings and enable GitHub PR integration using CodeScene's supported GitHub App flow. Confirm the app has access to this repository.
5. Verify an analysis result in CodeScene and, for PR integration, verify CodeScene posts a check/review on a newly opened or updated PR. The GitHub Actions jobs in this repository do not substitute for a CodeScene analysis.

If FluxQueue is not listed, check which GitHub account is connected to CodeScene and whether the CodeScene Access app installation includes this repository. Private repository analysis may depend on the CodeScene plan. Do not create a custom GitHub App or store a private key unless the CodeScene setup flow specifically requires it.

**Verification status (2026-10-29):** The FluxQueue project dashboard shows a successful analysis dated October 29, 2026, with average code health 9.4 and hotspot code health 9.6. The GitHub PR check is now verified: CodeScene posted `CodeScene Code Health Review (main)` on PR #17 and the latest review passed all three quality gates after the Doppler validator was refactored. See [latest CodeScene result](https://codescene.io/projects/87037/delta/results/8191366).

Official references:
- [CodeScene getting started](https://codescene.io/docs/getting-started/index.html)
- [CodeScene GitHub hosting integration](https://www.codescene.io/docs/providers/index.html)
- [CodeScene Access vs. Delta Analysis](https://helpcenter.codescene.com/articles/9262058-codescene-access-vs-codescene-delta-analysis-which-github-app-do)

## Controlled proxy-security verification

FluxQueue does not implement an outbound proxy, URL fetcher, redirect follower, DNS resolver, or SSRF protection layer. The repository's Nginx file is an example inbound reverse-proxy configuration (`deploy/nginx/fluxqueue.conf.example`), not a proxy implementation under test. Therefore DNS rebinding, unsafe destinations, redirect handling, malformed upstream responses, and proxy timeout behavior are not applicable repository tests and must not be claimed as passed. The example should be reviewed and tested separately in an authorized disposable deployment before public exposure.

## Copilot and Codex

Copilot and Codex are development assistants, not runtime dependencies. Keep their changes subject to the same tests, linting, migration checks, security analysis, and review gates as any other contribution. Never place production credentials in prompts or generated files.

## Current integration status

- GitHub Actions: configured; final PR CI run [40894751613](https://github.com/vankudothuadhinaik/FluxQueue/actions/runs/40894751613) passed all four jobs on commit `81b567b413a744044528af75d19d6772d19194aa`.
- CodeQL and Python dependency audit: passed in the final PR CI run above ([security](https://github.com/vankudothuadhinaik/FluxQueue/actions/runs/40894751613/job/123520688092), [dependency audit](https://github.com/vankudothuadhinaik/FluxQueue/actions/runs/40894751613/job/123520688002)).
- Codecov: coverage upload was accepted and queued for processing in run [40882641655](https://github.com/vankudothuadhinaik/FluxQueue/actions/runs/40882641655). The token exposed in the setup screenshot should be rotated and `CODECOV_TOKEN` updated; do not claim rotation is verified until a run succeeds with the replacement token.
- Doppler: project/config injection was reported verified in the PR's local smoke test; CI validates service wiring without requiring a Doppler token.
- CodeScene: PR integration is active; the final review on PR #17 passed ([CodeScene check](https://github.com/vankudothuadhinaik/FluxQueue/runs/123520649693), [analysis result](https://codescene.io/projects/87037/delta/results/8191366)).
- Render/other deployment: no production service is created by these files. Deploying a public service requires a deliberate environment, database, and cost decision.
