# Implementation plan

This ledger is **reconstructed**. Master-prompt Sections 14–16 and Appendix A are not in the repository copy. See `docs/DECISIONS.md` D-001. Do not treat a stage as complete until its acceptance checks have been run and recorded here.

Status words: **Implemented**, **Measured**, **Proposed**, **Assumed**, **Blocked**, **Not started**.

## Repository inspection (Measured)

Commands run on 2026-10-29 from the repository root:

- `git status --short` and `git log -5 --oneline`
  - Tracked file: `readme.Md` only (commits `3639167` Create readme.Md, `723b37d` removed licence from readme to test).
  - Untracked at inspection: `SUPPLYMIND_MASTER_BUILD_PROMPT.md`, `SupplyMind — Product Brief (v1 Scope).pdf`.
- `python --version` → Python 3.12.10
- `uv --version` → uv 0.11.32
- `docker --version` → Docker version 29.6.2; `docker compose version` → v5.3.1
- `docker info` at first check failed: the Docker Desktop engine pipe was not running. `com.docker.service` was Stopped. Docker Desktop was then launched. The schema-test result below records whether the engine became usable.
- `make` → not installed (D-012)
- `node --version` → v24.18.0; `npm --version` → 12.0.2
- `python -c` check → `uuid.uuid7` is absent (D-004)
- Master prompt file ends at Section 13.2. Product brief PDF is 5 pages and was read in full.

Preserved: `readme.Md`, the master prompt, and the product brief. No application code existed before this foundation.

## Stage 0 — Repository foundation

**Status:** Implemented as documentation and directory layout. This stage does not produce a running product.

**Objective:** agent rules, ledger, architecture, decisions, root config, and the directory skeleton.

**Prerequisites:** none.

**Acceptance:**

- `AGENTS.md` exists and states the authorities, the missing sections, and the conduct rules.
- `docs/DECISIONS.md` records the prompt/brief conflicts and the missing sections.
- `backend/`, `frontend/`, `docs/`, `scripts/`, `deploy/`, `e2e/`, and `.github/workflows/` exist.
- Root `Makefile`, `.env.example`, and `.gitignore` exist.
- The master prompt and product brief are unchanged.
- Frontend screens are not started.

**Files:** `AGENTS.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `docs/DECISIONS.md`, `Makefile`, `.env.example`, `.gitignore`, `.github/workflows/ci.yml`, `readme.Md` (status section only), `frontend/README.md`, `e2e/README.md`, `scripts/README.md`, `deploy/dev/compose.yml`, `deploy/test/compose.yml`, `deploy/prod/README.md`.

## Stage 1 — Backend platform

**Status:** Implemented. The checks in the command log below passed on 2026-10-29. This is not a business-feature API. Identity, inventory operations, risk math, providers, the worker, and the frontend are **Not started**.

**Objective:** Python 3.12 project, typed settings, database engine, application factory, Section 8 models, Alembic revision, test harness, and core security primitives.

**Prerequisites:** Stage 0.

**Out of scope for this stage:** signup/login, business endpoints, CSV parsing, risk math, provider calls, worker loop, frontend, deployment.

**Acceptance:**

- `uv lock` and `uv sync` succeed.
- `ruff check`, `ruff format --check`, `mypy`, `pytest`, `bandit`, and `pip-audit` exit 0. Record each command's result.
- Against PostgreSQL 16, `alembic upgrade head` and `downgrade base` succeed.
- After upgrade, model metadata matches the database.
- The database rejects a cross-workspace composite foreign key, a case-variant duplicate SKU, a case-variant duplicate email, a delivered order without a delivery date, a second open alert with the same dedupe key, and `UPDATE`/`DELETE` on `stock_adjustments` and `audit_log`.
- `GET /health` returns 200 and the security headers. Production settings reject placeholder secrets and the example database password.
- OpenAI model id and token prices have no code defaults.

**Not acceptance of this stage:** a working onboarding flow, a calculated risk, or a live email/FX/OpenAI integration.

## Stage 2 — Identity, sessions, CSRF, and workspace context

**Status:** Implemented. **Date:** 2026-10-29.

Registration creates a user, an `Africa/Lagos` / `NGN` workspace, an owner membership, workspace settings, and a server session in one transaction. Login, logout, session rotation, idle and absolute timeouts, and revoke-all are enforced. Session and CSRF secrets are stored as SHA-256 hashes. Cookie-authenticated unsafe routes require the CSRF header, with the four unauthenticated exceptions in D-017. The workspace id comes from the session membership. No new migration was added.

**Evidence:** `docs/API.md`, `docs/SECURITY.md`, D-017, and the command log below. Before these changes, `uv run pytest` was **41 passed**. After them, the same command was **74 passed**, including the Stage 1 schema tests.

**Not acceptance of this stage:** email delivery of password-reset tokens, email verification, catalog data, or the Section 9 isolation suite for resources that do not have routes yet. Application-layer tenancy is not row-level security.

## Later stages (Proposed, reconstructed)

Do not start a stage until the previous one's acceptance criteria are recorded as passed.

| Stage | Objective | Prerequisites |
|---|---|---|
| 3 | Vendors, products, primary/backup links, archive | Stage 2 |
| 4 | Append-only stock adjustments and ledger balance | Stage 3 |
| 5 | Orders, delivery, receipt adjustments, vendor lead-time inputs | Stage 4 |
| 6 | Sales CSV upload, preview, commit, coverage, optional stock deduction defaulting off | Stage 4 |
| 7 | Job queue and worker process | Stage 1 schema; needed before async risk, mail, and explanations |
| 8 | `docs/RISK_ENGINE.md` and the deterministic baseline engine, with an independent oracle of the Section 10.4 formula | Stages 4 and 5; sales data optional and labelled when missing |
| 9 | Seasonality calendar with cited dates, and FX. Live-verify at least two rate sources or keep manual entry and mark auto-update blocked | Stage 8 |
| 10 | Causal layer on networkx. Evaluate dowhy/pgmpy only if a measured gain is shown. No default β | Stages 8 and 9 |
| 11 | Alert lifecycle, dedupe, hysteresis, cooldown | Stage 8, jobs for async paths |
| 12 | Explanation provider, fallback, validation, cache, caps. Live OpenAI stays unverified without a real credential and a documented model id | Stage 11 |
| 13 | Email notifications over SMTP. Mailpit locally. Delivery without credentials is a tested failure, not a fake send | Stage 11 |
| 14 | Monitoring, audit completeness, rate limits on the expensive routes, bandit and pip-audit gate | Stages 2–13 as applicable |
| 15 | OpenAPI freeze for the built routes and generated TypeScript types | Stable routes from the stages above |
| 16 | Frontend application, after those contracts | Stage 15 for the screens being built |
| 17 | Playwright onboarding-to-alert path | Stages 15 and 16, plus the backend path under test |
| 18 | Deployment assets (Caddy, backup, restore). Writing them is not deploying them | Stage 1 at minimum; production cutover is a separate explicit action |
| 19 | Acceptance report against the brief's definition of done, including unmet pilot and unverified FX items | Evidence from earlier stages |

Each feature stage's acceptance is: the behaviour specified for it in Sections 7–13 or the product brief, tests for the happy path and the stated failure and tenancy cases, and commands recorded in this file. A stage that calls a third party is not accepted as a live integration unless a live call was made and recorded.

The product brief's pilot (3–5 businesses for 4 weeks) and the "Naira rate updates without manual work" criterion stay open. They are not implied by unit tests.

## Known gaps

- Sections 14–16 and Appendix A are missing (D-001).
- GNU make is not installed locally (D-012).
- No agreed AI monthly cap (D-008).
- No verified FX provider or rate type (D-002, D-010).
- No seasonal dates are seeded. Dates must be cited or marked `needs_verification`. None were invented.
- Password-reset email is not sent. The token API exists; delivery is Stage 13 (D-017).
- Email verification is not implemented.
- The Section 9 isolation suite for products, vendors, orders, imports, sales, alerts, snapshots, explanations, usage, and notifications waits for those routes. Settings are covered.
- Auth rate limits are in-process only and use the socket address, not a forwarded client IP.
- `TRUNCATE` on append-only tables is not blocked (D-011).

## Next valid stage

Stage 3 — vendors, products, primary and backup links, and archive. Do not start frontend screens. New tenant routes must add an isolation test or `tests/unit/test_auth_routes.py` fails.

## Command log

Inspection commands are in the first section. Backend commands below were run from `backend/` unless noted. GNU `make` is not installed, so `make check` was not run. The commands `make check` would invoke were run directly.

### Measured 2026-10-29

- `uv sync --all-groups` — exit 0. Resolved 82 packages. Wrote `backend/uv.lock` and `backend/.venv`.
- `uv run ruff check src tests migrations` — exit 0 (`All checks passed`).
- `uv run ruff format --check src tests migrations` — exit 0 (64 files already formatted).
- `uv run mypy` — exit 0 (`Success: no issues found in 50 source files`).
- `uv run bandit -c pyproject.toml -r src/supplymind` — exit 0. No issues identified. 1609 lines of code scanned.
- `uv run pip-audit` — exit 0. `No known vulnerabilities found`. The local project `supplymind` is not on PyPI and was skipped by the auditor.
- `uv run pytest` — exit 0. **41 passed**, 1 warning, 11.05s on the final run. An earlier run spent about 164s pulling PostgreSQL 16 and starting Testcontainers. The final run reused that image.
- From the repository root: `docker compose -f deploy/dev/compose.yml config --quiet` and the same for `deploy/test/compose.yml` — exit 0. This validates Compose syntax. It does not start containers or prove the Mailpit tag can be pulled.
- Docker Desktop was started during this session. `docker info` then reported server version 29.6.2.
- `docker manifest inspect axllent/mailpit:v1.21` — exit 0. The tag exists. The image was not pulled and Mailpit was not started.

Schema tests, against PostgreSQL 16:

- Alembic upgrade to `0001_initial_schema`, downgrade to `base`, and upgrade again.
- Reflected metadata matched the SQLAlchemy models (`compare_metadata` diff empty).
- The database rejected a cross-workspace product/vendor link, a case-variant duplicate SKU, a case-variant duplicate email, a delivered order without a delivery date, an unknown order status, a second open alert with the same dedupe key, `UPDATE` on `stock_adjustments`, and `DELETE` on `audit_log`.

Warning that did not fail the run: Starlette reports that `TestClient` on the installed `httpx` is deprecated in favour of a package it calls `httpx2`. No extra package was added for that warning.

`make check`, a pulled Mailpit image, a live OpenAI call, and a live FX call were not run.

### Measured 2026-10-29 — Stage 2

Commands were run from `backend/` unless noted. GNU `make` is still not installed.

- Before identity changes: `uv run pytest` — exit 0. **41 passed**, 1 warning, 18.82s.
- `uv run ruff check src tests migrations` — exit 0 (`All checks passed`).
- `uv run ruff format --check src tests migrations` — exit 0 (81 files already formatted).
- `uv run mypy` — exit 0 (`Success: no issues found in 64 source files`).
- `uv run bandit -c pyproject.toml -r src/supplymind` — exit 0. No issues identified. 2910 lines of code scanned.
- `uv run pip-audit` — exit 0. `No known vulnerabilities found`. The local project `supplymind` is not on PyPI and was skipped.
- `uv run pytest` — exit 0. **74 passed**, 1 warning, 16.45s. This includes `test_migrated_schema_matches_models` and `test_migration_downgrade_and_upgrade` against PostgreSQL 16. No Alembic revision was added. `0001_initial_schema` was not edited. Alembic was not run as a separate CLI outside pytest.
- From the repository root: `docker compose -f deploy/dev/compose.yml config --quiet` and the same for `deploy/test/compose.yml` — exit 0.
- `make --version` — failed. PowerShell reported `make` is not recognized. `make check` was not run.

The same Starlette `TestClient` / `httpx` deprecation warning remains. No package was added for it. No dependency was added; `uv.lock` was not changed.

An intermediate identity pytest run failed 5 tests because a second registration in the same client sent the first session cookie and revoked it. The tests were corrected. The 74-passed run is the one above.
