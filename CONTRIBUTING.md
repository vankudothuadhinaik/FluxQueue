# Contributing

1. Create a focused branch from `main`.
2. Use Python 3.12+ and install `pip install -e '.[dev]'`.
3. Run `ruff check .`, `ruff format --check .`, and `pytest`.
4. Add regression tests for bugs and behavior changes.
5. Never commit secrets, generated databases, or unverified benchmark claims.
6. Keep README and failure-model docs aligned with implemented behavior.
