# Architecture

**Status:** the boundaries below are the locked design from master-prompt Sections 5–7. Only the backend platform slice is implemented. Everything else in this document is **Proposed** unless a section says **Implemented**.

## System

SupplyMind v1 is a modular monolith:

- One FastAPI backend in `backend/`
- One React frontend in `frontend/` (**not started**)
- One PostgreSQL 16 database
- One worker process, later, from the same backend codebase, using a `jobs` table and `SELECT … FOR UPDATE SKIP LOCKED`

Not in v1: Redis, Celery, another message broker, microservices, Kubernetes, a customer-facing public API, automated purchasing, and a language model that calculates risk.

```text
Browser (not started)
    |  HTTPS, cookie session, CSRF header on mutations
    v
FastAPI  /api/v1          Implemented: process, config, probes, error envelope
    |                     Proposed: identity, catalog, inventory, sales, orders,
    |                               signals, risk, alerts, explanations, notifications
    v
PostgreSQL 16             Implemented: schema and append-only triggers
    ^
Worker (not started) -----+---- OpenAI (unverified) and FX source (unverified)
```

Tenancy is enforced in the application: a `TenantContext`, repositories that require it, composite foreign keys `(workspace_id, parent_id)`, and tests that try cross-workspace references. PostgreSQL row-level security is a future option and is not built.

The workspace id used for authorisation will come from the server session, not from a body or URL field. Resource ids will be loaded through tenant-scoped repositories so another workspace's id is a 404. That authorisation path is **not implemented** yet. The schema rules that make cross-workspace foreign keys fail are **Implemented** and covered by database tests when PostgreSQL is available.

## Backend layout

**Implemented**

- `backend/src/supplymind/main.py` — application factory, probes, error envelope, request id, security headers, CORS
- `config.py` — typed settings
- `clock.py` — injectable clock
- `db/` — engine, session, metadata, model registry
- `core/` — password hashing, token hashing, CSRF compare, IP HMAC, tenancy type, errors, JSON logs, in-process rate limiter, pagination, ids
- `modules/*/models.py` — Section 8 tables
- `migrations/` — initial revision
- `backend/tests/` — unit tests and PostgreSQL schema tests

**Not started:** routers, services, repositories for each module, the risk engine, providers, the worker, and the route-level isolation suite.

Routers will validate and authorise. Services will hold business rules and will take a `Clock`. Repositories will be the only code that uses the SQLAlchemy session and will require `TenantContext`. Business code will not call `datetime.now()`.

## API conventions (Proposed, from Section 7)

- JSON under `/api/v1`, except CSV upload which will be multipart
- Page envelope `{items, page, page_size, total}` with `page_size` at most 100
- Errors `{error: {code, message, details?, request_id}}`
- Mutating requests will require the CSRF header once identity exists
- Idempotency for import commit, job enqueue, and alert creation will follow Sections 7 and 10.7. Section 14's further idempotency text is missing and is not guessed.

`GET /health` and `GET /ready` are probes outside `/api/v1` (D-013).

## Data

Tenant tables carry `workspace_id`. Child rows reference parents with composite foreign keys. Money and quantities use the numeric types in D-005. Timestamps are `timestamptz` in UTC. Business dates are `date`. Products and vendors use `archived_at` rather than hard deletes.

`stock_adjustments` and `audit_log` are append-only at the database for `UPDATE` and `DELETE`.

The risk engine, when built, stays behind `modules/risk`. A language-model adapter may only explain a stored snapshot. Numbers in the UI will be read from the snapshot, not from model prose.

## Configuration and environments

`APP_ENV` is `development`, `test`, or `production`. Provider selection will be configuration, not scattered `if APP_ENV` checks in business code.

- `development` — Compose PostgreSQL and Mailpit (`deploy/dev/compose.yml`)
- `test` — ephemeral PostgreSQL; external services mocked. Live calls are out of the default test run.
- `production` — **Proposed:** one Compose stack behind Caddy, with backups. Not written and not deployed.

Secrets have no code defaults. See `.env.example` and D-010.

## Logging

**Implemented:** JSON logs with `request_id`, without query strings. Unhandled errors return a generic message and no stack trace. Readiness failures do not return the driver exception text.

## Frontend (not started)

The intended stack is React 18, TypeScript strict, Vite, React Router, TanStack Query, React Hook Form, Zod, Tailwind CSS, accessible UI primitives, and Recharts. Types will be generated from OpenAPI with `openapi-typescript` after the relevant contract is stable. No package is installed in this stage.

## Worker (not started)

The `jobs` table and its partial unique index exist so a later worker can claim rows with `SKIP LOCKED`. No worker process runs.

## Deployment (not started)

Do not treat `deploy/prod/README.md` as a deployment. Production hosting in the master prompt is one small VPS, Caddy, containerised PostgreSQL, and `pg_dump` to S3-compatible storage. None of that has been provisioned.
