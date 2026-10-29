# SupplyMind backend

Python 3.12 service for SupplyMind. This package contains configuration, the application factory, the Section 8 schema, and Stage 2 identity: registration, sessions, CSRF, and the current workspace. It does not implement inventory operations or the risk engine.

Identity contracts are in `docs/API.md`. Session and CSRF rules are in `docs/SECURITY.md`. Apply the existing migration with `uv run alembic upgrade head`. Stage 2 did not add a revision.

Run commands from the repository root with `make`, or from `backend/` with `uv`. GNU make was not available on the machine that created this tree; the ledger records the commands that were actually run.

```text
uv sync --all-groups
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy
uv run pytest
uv run bandit -c pyproject.toml -r src/supplymind
uv run pip-audit
```

Local PostgreSQL and Mailpit, when Docker is running:

```text
docker compose -f deploy/dev/compose.yml up
```

That compose file starts dependencies only. It does not build or deploy the API.

Apply migrations after `APP_SECRET` and `DATABASE_URL` are set in the root `.env` (see `.env.example`):

```text
uv run alembic upgrade head
```

Development server, after that environment exists:

```text
uv run uvicorn supplymind.main:create_app --factory --app-dir src --host 127.0.0.1 --port 8000
```

`GET /health` does not check the database. `GET /ready` does. Neither route is a product API.
