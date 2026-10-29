# SUPPLYMIND V1 — MASTER BUILD PROMPT

**Audience:** an autonomous coding agent (or capable coding AI) that will build SupplyMind v1.
**Authority:** this document is the implementation contract. Read it fully before acting. Re-read Sections 1, 2, 14 and the current stage every time you resume work.
**Source product authority:** the SupplyMind PRD / Product Brief (v1 MVP), condensed in Appendix A. If the repository contains a newer copy, read it, record differences in `docs/DECISIONS.md`, and follow this prompt where the two conflict on engineering, and the PRD where they conflict on product scope.

---

## 1. YOUR ROLE AND MISSION

You are acting as Principal Software Architect, Senior Full-Stack Engineer, AI Systems Engineer, QA Lead and DevOps Engineer on one project: **build SupplyMind v1 end to end**, from an empty or partially built repository to a tested, documented, deployable application.

SupplyMind is an AI-powered inventory risk platform for small and medium businesses that sell physical goods. A business signs up, enters its inventory, vendors, orders and sales history, picks the risk factors that matter to it, and SupplyMind tells it which products may run out of stock, why, and what to consider doing, before the shortage happens.

You will work in ordered stages (Section 16 onward). You will verify each stage with real commands before calling it complete. You will keep a ledger so that you can resume after interruption. You will finish with an evidence-based completion report.

## 2. NON-NEGOTIABLE RULES

### 2.1 Truthfulness and evidence
1. Never claim a command passed unless you ran it and observed the result in this session. Paste the command and the relevant output summary into the ledger.
2. Never fabricate test results, benchmarks, accuracy figures, pilot customers, pilot outcomes, deployment evidence, API credentials, data-provider availability, or causal relationships.
3. Label every statement in documentation and reports as one of: **Implemented** (code exists and tests pass), **Measured** (a result you produced by running something, with the command), **Proposed** (designed, not built), or **Assumed** (not verified).
4. Mocked provider tests prove your code handles that provider's contract. They do not prove the live integration works. Say so wherever it matters.
5. Synthetic or demo data must be labelled synthetic everywhere it appears (files, UI banners, reports). Never present backtest results on synthetic data as evidence of real-world accuracy.
6. Targets in this document (20-minute onboarding, 20 reference products, risk thresholds, confidence cut-offs) are **acceptance targets to validate**, not results.

### 2.2 Engineering conduct
1. Do not stop to ask about routine decisions. Decide, record the decision in `docs/DECISIONS.md`, and continue.
2. Stop and report only for a genuine blocker (Section 14.6).
3. Diagnose root causes. Never fix a failing test by deleting it, weakening its assertion, skipping it, or loosening a security control.
4. Never leave a feature "complete" with placeholder, TODO-stubbed, hard-coded, or mock-only behaviour in the production path.
5. No destructive repository operations (force-push, history rewrite, deleting user files, dropping non-test databases) without explicit authorization.
6. Never print, log, commit or echo secret values. When auditing environment files, report only the names of variables and whether they are set.
7. Keep code, migrations, tests and documentation synchronized in the same stage.

### 2.3 Product boundaries
1. SupplyMind **suggests**; it never purchases, never sends purchase orders to vendors, and has no code path that does.
2. The backend risk engine is the only source of numbers shown to users. A language model writes prose about those numbers and never produces, alters or recalculates them.
3. When evidence is insufficient, say so in the product. Do not manufacture precise-looking probabilities, causal contributions or confidence.

---

## 3. PRODUCT CONTEXT

**Users:** owners and managers of small and medium businesses (retail shops, distributors) that hold physical stock and buy from vendors, primarily in Nigeria. Currency is Naira (NGN). Dates in the UI default to DD/MM/YYYY display with ISO 8601 storage. Time zone default `Africa/Lagos`, stored as UTC.

**Core value:** anticipate stock-outs, explain contributing factors in plain language, and propose an action in time to act.

**Primary workflow (must work end to end):**
1. Sign up; a workspace is created.
2. Onboarding: company info, vendors, products (linked to vendors, with reorder thresholds and stock), optional sales-history CSV, risk factor selection.
3. The risk engine computes product-level stock-out risk.
4. The dashboard shows a prioritised list, with the contributing factors and data freshness.
5. The explanation layer writes a plain-language explanation and suggested action from verified backend facts.
6. Alerts are raised when thresholds are crossed; email notifications are sent.
7. The business reviews inventory, vendors, orders, alerts and history.
8. AI usage is metered and capped per workspace.

---

## 4. SCOPE

### 4.1 In scope (v1)
A. Accounts and workspaces. B. Onboarding. C. Inventory management and CSV sales import. D. Vendor management, order tracking, vendor reliability. E. Three risk factors: vendor reliability, Naira exchange rate, demand seasonality. F. Inventory risk engine with documented baseline, forecasting method, and a causal layer that actually drives calculations. G. OpenAI explanation layer. H. Dashboard and alerts with email. I. Monitoring, scheduled recalculation, audit records, and cost controls.

### 4.2 Explicit non-goals (do not build, do not scaffold, do not stub)
- Automated purchasing or purchase-order sending.
- ERP or third-party inventory-system integrations; a public API product or API keys for customers.
- Free-text AI chat assistant; natural-language scenario simulator.
- Port congestion or any external signal without a validated, appropriate data source.
- Training or hosting a language model.
- Microservices, message brokers, Kubernetes, or any recurring-cost infrastructure not justified in Section 5.
- Multiple users per workspace with roles beyond `owner` (the schema supports memberships; the v1 UI and API support one owner).

Keep seams for the future (provider interfaces, a `membership` table, versioned API) without implementing the future features.

### 4.3 Deliberate deviations from the PRD wording (recorded decisions)
- **Onboarding order:** the PRD lists products before vendors. A product needs a vendor link, so the wizard runs **company → vendors → products → sales history (optional) → risk factors → finish**. The product form also allows creating a vendor inline.
- **Sales vs stock:** a sales-history CSV feeds demand estimation only. On-hand stock changes only through auditable stock adjustments (including automatic "receipt" adjustments when an order is marked delivered). An opt-in checkbox on import may also deduct imported sales from stock; default off.

---

## 5. LOCKED ARCHITECTURE AND STACK

A **modular monolith** with one backend codebase, one frontend codebase, one PostgreSQL database, and one background worker process that runs from the same backend codebase. Do not substitute these without recording a justified decision and a passing build.

| Concern | Decision | Why it fits | Cost / complexity | Boundary |
|---|---|---|---|---|
| Language/runtime | Python 3.12 | Data/ML ecosystem for the risk engine and causal libraries | Low | Backend only |
| API framework | FastAPI + Pydantic v2 | Typed schemas, automatic OpenAPI, async I/O | Low | `/api/v1` |
| ORM / migrations | SQLAlchemy 2.0 (typed) + Alembic | Mature, explicit, testable migrations | Low | `db/` package only; routers never build raw queries |
| Database | PostgreSQL 16 | Relational integrity, partial unique indexes, `SKIP LOCKED` job queue, JSONB | One small instance | `DATABASE_URL` |
| Background jobs | Postgres-backed `jobs` table + a worker process using `SELECT … FOR UPDATE SKIP LOCKED`, with an in-worker scheduler | Avoids Redis/Celery cost and ops burden at v1 scale; idempotent and inspectable | Low | `supplymind.jobs` |
| Numerics | numpy, scipy, pandas (only where it clearly helps) | Hand-checkable math, reference oracle | Low | `modules/risk` |
| Causal layer | `networkx` for the explicit DAG + a small structural-equation implementation in numpy/scipy. Evaluate `dowhy` and `pgmpy` (Stage 9): use them only where they add verified value (e.g. refutation tests, parameter estimation); otherwise do not add the dependency | A library does not create causality; the graph must drive the calculation | Low | `modules/risk/causal` |
| Auth | Server-side sessions in Postgres, `HttpOnly` + `Secure` + `SameSite=Lax` cookie, `argon2-cffi` password hashing, CSRF token header on mutating requests | Revocable, no token storage in JS | Low | `modules/identity` |
| Email | `EmailProvider` interface; one implementation over **SMTP** (Mailpit locally; any SMTP provider in production) | Cheapest, no vendor lock-in | Free tier typical | `modules/notifications` |
| LLM | `ExplanationProvider` interface; OpenAI adapter using the official `openai` SDK and structured outputs; model id, price table and limits in configuration | Do not train a model; replaceable | Pay per use, capped | `modules/explanations` |
| FX data | `FxRateProvider` interface; provider chosen in Stage 8 after live verification | Source reliability is the main risk | Prefer free tier | `modules/signals` |
| Frontend | React 18 + TypeScript (strict) + Vite; React Router; TanStack Query; React Hook Form + Zod; Tailwind CSS with shadcn/ui primitives; Recharts | Productive, testable, accessible components | Low | `frontend/` |
| API types | OpenAPI schema → `openapi-typescript`, committed generated types checked in CI | One source of truth for contracts | Low | `frontend/src/api` |
| Backend tests | pytest, pytest-asyncio, httpx `AsyncClient`, Testcontainers or a dedicated test Postgres, `freezegun`/injected clocks, `respx` for HTTP mocking | Real DB tests, deterministic time | Low | `backend/tests` |
| Frontend tests | Vitest + React Testing Library; MSW for network | Standard | Low | `frontend/src` |
| E2E | Playwright against a full local stack | Onboarding-to-alert proof | Low | `e2e/` |
| Quality tools | ruff (lint+format), mypy (strict on `modules/risk`, `core`), bandit, pip-audit; ESLint, Prettier, `tsc --noEmit`, `npm audit`; optional gitleaks | Static gates | Low | `Makefile` |
| Packaging | `uv` with `pyproject.toml` and a lock file; `npm` with a lock file | Reproducible | Low | — |
| Containers | Docker + Docker Compose (`dev`, `test`, `prod` compose files) | Reproducible local and deployed environments | Low | `deploy/` |
| Production hosting | One small VPS running Docker Compose behind **Caddy** (automatic TLS), PostgreSQL in a container with a mounted volume, nightly `pg_dump` to S3-compatible storage. Document the upgrade path to managed Postgres | Lowest recurring cost; deployable by a small team | One small VM | `deploy/prod` |
| CI | GitHub Actions workflow running `make check` (adapt only if the repository is hosted elsewhere) | Enforces gates | Free tier | `.github/workflows` |
| Rate limiting | In-process limiter keyed by IP and user for auth and expensive endpoints (single-instance v1; document the limitation) | Avoids Redis | Low | `core/rate_limit.py` |

**Row-level security:** v1 enforces tenancy in the application layer with a mandatory tenant context, tenant-scoped repositories, composite foreign keys, and cross-workspace tests. PostgreSQL RLS is recorded as a future hardening option, not built in v1.

---

## 6. REPOSITORY STRUCTURE (target)

If the repository is not empty, apply Stage 0 first and adapt; preserve existing conventions where they do not conflict with a locked decision.

```
supplymind/
├── IMPLEMENTATION_PLAN.md          # the ledger (Section 14)
├── ARCHITECTURE.md
├── README.md
├── Makefile                        # setup, dev, lint, typecheck, test, test-backend, test-frontend, e2e, migrate, check
├── .env.example                    # names only, no secrets
├── .github/workflows/ci.yml
├── backend/
│   ├── pyproject.toml  uv.lock  alembic.ini
│   ├── migrations/versions/
│   ├── src/supplymind/
│   │   ├── main.py                 # app factory, middleware, router mounting
│   │   ├── config.py               # typed settings (pydantic-settings)
│   │   ├── clock.py                # injectable clock
│   │   ├── db/                     # engine, session, base, mixins
│   │   ├── core/                   # security, tenancy, errors, logging, rate_limit, pagination, ids
│   │   └── modules/
│   │       ├── identity/           # users, sessions, password reset
│   │       ├── workspaces/         # workspaces, memberships, settings
│   │       ├── onboarding/
│   │       ├── catalog/            # products, vendors, product_vendors
│   │       ├── inventory/          # stock adjustments, ledger
│   │       ├── sales/              # sales_daily, csv imports
│   │       ├── orders/             # orders, lines, vendor reliability
│   │       ├── signals/            # fx providers, seasonality calendar, freshness
│   │       ├── risk/               # inputs, baseline, demand, causal/, engine, backtest/
│   │       ├── alerts/
│   │       ├── explanations/       # provider interface, openai adapter, schema, validation, cache, usage
│   │       ├── notifications/
│   │       ├── jobs/               # queue, worker, scheduler, handlers
│   │       └── audit/
│   └── tests/ {unit,integration,api,security,fixtures}/
├── frontend/                       # Vite + React + TS
│   └── src/ {api,components,features,pages,routes,lib,test}/
├── e2e/                            # Playwright
├── scripts/                        # seed_demo (synthetic), reference-case tools, backtest runner
├── deploy/ {dev,test,prod}/        # compose files, Caddyfile, backup scripts
└── docs/ {DECISIONS.md, RISK_ENGINE.md, SECURITY.md, API.md, RUNBOOK.md, DEPLOYMENT.md, KNOWN_LIMITATIONS.md, ACCEPTANCE_REPORT.md, audit/}
```

---

## 7. CONVENTIONS

**API:** REST under `/api/v1`. JSON only (CSV upload is multipart). Resource nouns, plural. Cursor or page/size pagination (`page`, `page_size` ≤ 100) with a consistent envelope `{items, page, page_size, total}`. Errors use one shape: `{error: {code, message, details?, request_id}}` with stable machine codes; never leak stack traces or SQL. Mutating requests require the CSRF header. Idempotency: `POST /imports/{id}/commit`, job enqueueing and alert creation are idempotent by design (Section 14). Version-bump `/api/v2` only for breaking changes.

**Database:** every tenant table has `workspace_id NOT NULL`, `id` (UUID v7 or UUID4), `created_at`, `updated_at`. Child tables reference parents with **composite foreign keys** `(workspace_id, parent_id)` so a row can never point at another workspace's parent. Money in `NUMERIC(14,2)` with currency code; quantities in `NUMERIC(14,3)` (some goods are fractional) unless Stage 4 decides integers only and records why. Timestamps `timestamptz` in UTC; business dates `date`. Soft-delete via `archived_at` for products and vendors. Alembic migrations are linear, reversible where feasible, and never edited after merge. Unique and partial unique indexes enforce invariants (Section 8.2).

**Access pattern:** routers → services → repositories. Routers validate and authorise; services hold business logic; repositories are the only code that touches SQLAlchemy sessions and **always** take a `TenantContext(workspace_id)` argument. A repository method without a tenant context is a defect.

**Configuration:** typed `Settings` loaded from environment variables; `.env.example` lists every variable with a comment; the app fails fast on missing required production variables. Secrets are never defaulted. Separate `APP_ENV` values: `development`, `test`, `production`. Feature behaviour that varies by environment (email transport, FX provider mocks, OpenAI) is selected by configuration, never by `if APP_ENV` scattered in business code.

**Logging:** structured JSON logs, `request_id` on every request and propagated to jobs, no secrets or full personal data, log levels used consistently. Errors in jobs record `attempts`, `last_error` (truncated), and are visible in an admin-only diagnostics endpoint or CLI.

**Errors:** domain exceptions mapped to HTTP codes in one handler; validation errors return field-level details.

**Dependencies:** pin via lock files; add a dependency only with a one-line justification in `docs/DECISIONS.md`; run `pip-audit` and `npm audit` in `make check`.

**Environments:** `development` (Compose with Postgres, Mailpit, optional stub providers), `test` (ephemeral Postgres, all external services mocked), `production` (Compose behind Caddy). The test suite must never call real external services unless explicitly marked `live` and skipped without credentials.

**Time:** all business logic takes a `Clock` dependency. Never call `datetime.now()` inside services or the risk engine.

---

## 8. DATA MODEL

### 8.1 Tables (names are guidance; keep the semantics)
All tenant tables carry `workspace_id`.

| Table | Purpose / key columns |
|---|---|
| `users` | email (unique, case-insensitive), password_hash, email_verified_at, is_active |
| `sessions` | user_id, token_hash, expires_at, revoked_at, user_agent, ip (hashed or truncated) |
| `password_reset_tokens` | user_id, token_hash, expires_at, used_at |
| `workspaces` | name, industry, size_band, timezone, currency (default NGN), onboarding_step, onboarding_completed_at |
| `memberships` | user_id, workspace_id, role (`owner`) |
| `workspace_settings` | enabled_risk_factors (set of `vendor_reliability`,`fx_rate`,`seasonality`), alert thresholds, notification prefs (recipient emails, cooldown hours), `ai_monthly_token_cap`, `ai_monthly_cost_cap`, risk recalculation interval |
| `vendors` | name, contact fields, typical_lead_time_days, imports_goods (bool: exposed to FX), archived_at |
| `products` | sku (unique per workspace), name, unit, current_stock, reorder_threshold, unit_cost (optional), archived_at |
| `product_vendors` | product_id, vendor_id, role (`primary`/`backup`), (at most one primary per product) |
| `stock_adjustments` | product_id, delta, reason (`manual_count`,`receipt`,`sale_deduction`,`damage`,`correction`,`initial`), note, actor_user_id, balance_after, source_ref (e.g. order_line_id/import_id) — append-only ledger |
| `csv_imports` | status (`uploaded`,`previewed`,`committed`,`failed`,`expired`), file_sha256, original_name, date_format, duplicate_policy, row counts, error summary, deduct_from_stock flag |
| `csv_import_rows` | import_id, row_number, parsed values, status (`valid`,`error`,`duplicate`,`unknown_sku`), error_code |
| `sales_daily` | product_id, sale_date, quantity, import_id (nullable), unique (workspace, product, sale_date) |
| `sales_coverage` | product_id, covered_from, covered_to — distinguishes **zero sales** from **no data** |
| `orders` | vendor_id, order_date, expected_date, actual_delivery_date, status (`open`,`delivered`,`cancelled`) |
| `order_lines` | order_id, product_id, qty_ordered, qty_received |
| `fx_rates` | (global table) pair (`USD/NGN`), rate, rate_type (documented), observed_on, source, fetched_at, raw_ref |
| `seasonal_events` | (global seed table) code, name, start/end rule or concrete dated occurrences, region, source note |
| `risk_snapshots` | product_id, computed_at, inputs_hash, engine_version, stockout_probability, risk_band, days_of_cover, confidence, evidence JSON, contributions JSON, data_quality JSON |
| `alerts` | product_id, alert_type, severity, status, opened_at, acknowledged_at, resolved_at, snapshot_id, dedupe_key |
| `explanations` | snapshot_id, input_hash, schema_version, content JSON, source (`ai`/`fallback`), provider, model, prompt_tokens, completion_tokens, estimated_cost, created_at |
| `ai_usage` | period (month), requests, prompt_tokens, completion_tokens, estimated_cost, blocked_requests |
| `notifications` | alert_id, event (`opened`,`escalated`), recipient, status, attempts, last_error, provider_message_id, next_attempt_at |
| `jobs` | type, payload, dedupe_key, run_at, status, attempts, locked_by, locked_at, last_error |
| `audit_log` | actor, action, entity_type, entity_id, before/after JSON (no secrets), request_id |

### 8.2 Invariants enforced by the database
- Composite FKs `(workspace_id, id)` on every child reference.
- `UNIQUE (workspace_id, lower(sku))` on products; one `primary` vendor per product (partial unique index); a backup vendor cannot equal the primary.
- `UNIQUE (workspace_id, product_id, sale_date)` on `sales_daily`.
- Partial unique index on `alerts (workspace_id, dedupe_key) WHERE status IN ('open','acknowledged')`.
- Partial unique index on `jobs (dedupe_key) WHERE status IN ('pending','running')`.
- `UNIQUE (alert_id, event, recipient)` on notifications.
- Check constraints: non-negative thresholds and lead times; `delivered` orders have an actual delivery date.
- `stock_adjustments` and `audit_log` are append-only (no update/delete path in code; add DB triggers or revoke privileges if practical).

---

## 9. SECURITY AND MULTI-TENANCY REQUIREMENTS

1. **Authentication:** argon2id hashing; minimum password policy (length ≥ 10, breach-list check optional); constant-time comparison; generic login errors (no account enumeration); session rotation on login; absolute and idle session timeouts configurable; logout and "revoke all sessions".
2. **Password reset:** single-use, hashed, short-lived tokens; reset responses never reveal whether an email exists; email verification required before email notifications are enabled.
3. **CSRF/CORS:** CSRF header required for mutating requests; CORS restricted to configured origins; cookies `Secure` in production.
4. **Authorization:** every endpoint resolves the current user → membership → workspace. The workspace id is **never taken from request bodies or URLs as a trust source**; it comes from the session. Resource ids in URLs are looked up through tenant-scoped repositories so another tenant's id returns `404`.
5. **Tenant isolation proof:** automated tests create two workspaces and prove, for **every** resource type (products, vendors, orders, imports, sales, alerts, snapshots, explanations, usage, notifications, settings), that workspace B cannot read, list, update, delete, or reference workspace A's records, including via filters, search, pagination, bulk endpoints, CSV imports and job payloads. A test enumerates all registered routes and fails if a tenant-data route lacks an isolation test entry.
6. **Input validation:** Pydantic schemas with bounds; reject unknown fields on write schemas; length limits; safe pagination caps.
7. **CSV safety:** size and row caps (configurable; defaults 5 MB / 50,000 rows), MIME and extension checks, UTF-8 (with BOM) handling, streaming parse, CSV/formula injection neutralised on any export or echo (prefix `'` for cells beginning with `= + - @`), no path traversal, files not retained after parsing beyond the staged rows, `file_sha256` duplicate detection.
8. **External API responses** (FX, OpenAI): timeouts, size caps, schema validation, never trusted blindly; failures degrade explicitly (stale flags, fallback text).
9. **Secrets:** environment variables only; `.env` git-ignored; startup refuses to run in production with default/empty secrets; logs and error responses scrub secrets; OpenAI key never reaches the frontend bundle (a test greps the built frontend for key patterns and env names).
10. **Rate limiting:** login, signup, password reset, CSV upload, and any endpoint that can trigger an LLM call.
11. **Privacy-conscious AI requests:** see Section 12.3.
12. **Audit:** record sign-in events, stock adjustments, product/vendor/order changes, settings changes, imports, alert state changes, and AI cap blocks, with actor and request id.
13. **Transactions:** multi-row business operations (CSV commit, order delivery with stock receipt, stock adjustment) run in a single transaction with row locking where concurrent edits are possible.
14. **Security headers:** `Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, HSTS in production, served via Caddy and verified in Stage 15.
15. Run `bandit`, `pip-audit`, `npm audit` and record unresolved findings with a justification; high-severity findings block Stage 14.

---

## 10. RISK ENGINE SPECIFICATION

The engine has four clearly separated layers. Never blur them in code, tests, documentation or UI copy.

1. **Deterministic inventory arithmetic** (days of cover, incoming stock, reorder point comparisons).
2. **Statistical estimation** (demand rate and variability, lead-time and lateness distributions).
3. **Causal reasoning** (a documented DAG whose structural equations modify the demand and arrival distributions; contributions via interventions) — Section 11.
4. **Language generation** (prose about verified results) — Section 12.

Write `docs/RISK_ENGINE.md` before or with Stage 7, and keep it synchronized with the code. It must contain the formulas below as final implemented.

### 10.1 Inputs (per product, at time `t`, all via the injected clock)
- `S`: on-hand stock from the ledger.
- Sales series from `sales_daily` plus `sales_coverage`. A day inside coverage with no row means **zero** sales; a day outside coverage means **unknown** and is excluded from estimation.
- Open orders containing this product: quantity outstanding and expected date.
- Vendor lead-time history from delivered orders: `lead = actual_delivery_date − order_date`; lateness `δ = actual − expected`.
- Vendor `typical_lead_time_days`.
- Reorder threshold.
- Enabled factors and their data freshness (Section 13).

### 10.2 Demand estimate (documented baseline, appropriate for limited SME data)
- Lookback window `W` (default 56 days, configurable) over covered days only.
- Daily demand mean `d̂`: exponentially weighted mean with half-life `H` (default 14 days) so recent days count more; fall back to the simple mean when fewer than 14 covered days.
- Daily demand standard deviation `σ̂`: weighted standard deviation of the same series.
- Sparse series handling: if at least 70% of covered days are zero, mark `demand_pattern = intermittent`, keep the same estimator, apply a confidence penalty, and surface a warning (v1 does not implement Croston or other intermittent-demand methods; record it as a known limitation).
- Minimum evidence: fewer than 14 covered days → `demand_status = insufficient`; the engine returns an `insufficient_evidence` result with **no probability** (only days-of-cover if any sales exist, labelled provisional). Zero estimated demand with adequate coverage → no stock-out risk from demand, risk band `low`, `days_of_cover = ∞` represented as `null` plus a flag.

### 10.3 Replenishment arrival time `A` (days from now)
- If an **open order** for the product exists with expected date `e` (days from now, floored at 0): `A = e + δ`, where `δ` is drawn from the vendor's empirical lateness distribution (completed orders, `n_vendor`). With `n_vendor < 5`, treat `δ = 0` and apply the confidence cap in 10.6.
- If **no open order** exists: `A = L`, the time a new order placed today would take: empirical lead-time distribution of the primary vendor when `n_vendor ≥ 5`, else the point mass `typical_lead_time_days` with the confidence cap.
- Represent the distribution of `A` as a discrete pmf over integer days: `w_a = P(A = a)`.
- Backup vendor: used only for suggested actions (e.g. "backup vendor typically delivers in X days"), never to lower the computed risk.

### 10.4 Stock-out probability (the baseline model)
Define the risk of stock-out before the next replenishment arrives:

```
P(stockout) = Σ_a  w_a · P( D(a) ≥ S_eff )
D(a) ~ Normal( μ = d̂_m · a ,  σ² = σ̂² · a )          (demand over a days)
S_eff = S                                               (open orders are modelled through A, not added to S)
```

where `d̂_m = d̂ · m` and `m` is the seasonality demand multiplier (Section 11). When `σ̂ = 0`, `P(D(a) ≥ S)` is the step function `1[d̂_m·a ≥ S]`. Use the normal CDF from scipy. Assumptions (independent daily demand, normal approximation) are documented as limitations; the reference oracle (Section 15.3) uses the same formula computed independently.

Derived values:
- `days_of_cover = S / d̂_m` (null when `d̂_m = 0`).
- `expected_shortfall_days = max(0, E[A] − days_of_cover)`.
- Risk bands (defaults, configurable per workspace, **not calibrated truth**): `low < 0.25 ≤ medium < 0.50 ≤ high < 0.80 ≤ critical`.
- Reorder-point rule: if `S ≤ reorder_threshold`, raise a separate `reorder_point_reached` alert type regardless of the probability band.
- Suggested reorder quantity (a suggestion, never an order): `max(0, ceil(d̂_m · (P80(L) + safety_days) − S − outstanding_qty))` with `safety_days` configurable (default 3); show unit cost × quantity when `unit_cost` exists.

### 10.5 What the UI may show
- Always: risk band, days of cover, expected arrival, confidence, evidence tier of each factor, data freshness.
- The **estimated chance** (percentage rounded to the nearest 5%) only when `confidence ≥ medium`; with low confidence show the band and "limited data" only.
- Never show a contribution percentage for a factor whose evidence tier is `insufficient` or whose data is stale.

### 10.6 Confidence indicator (documented, deterministic)
Score from 0–100 built from named components; map to `low` (<40), `medium` (40–69), `high` (≥70). Defaults, all configurable and documented in `RISK_ENGINE.md`:
- Covered sales days: ≥ 56 → 30 pts; 28–55 → 20; 14–27 → 10; < 14 → 0 (and result becomes `insufficient_evidence`).
- Demand regularity: not intermittent → 15; intermittent → 0.
- Vendor lead-time evidence: `n_vendor ≥ 10` → 25; 5–9 → 15; < 5 → 0 and **confidence is capped at `medium`**.
- Data freshness: sales coverage ends within 7 days → 20; 8–21 days → 10; older → 0.
- Stock-count recency: last stock adjustment within 14 days → 10; older → 0.
Every snapshot stores the component breakdown in `data_quality`.

### 10.7 Recalculation, idempotency and alert rules
- `inputs_hash` = hash of every input to the calculation plus `engine_version`. If a recalculation produces the same hash, do not create a new snapshot.
- Triggers: scheduled interval (default every 60 minutes, configurable), and change events (stock adjustment, sales commit, order create/update/deliver, settings change, FX refresh). Change events enqueue a deduplicated job per product with a short debounce.
- Alert lifecycle: `open → acknowledged → resolved`, plus `auto_resolved` when the band stays below the resolve threshold (hysteresis: resolve only when probability falls ≥ 0.05 below the band's lower edge, to prevent flapping).
- Deduplication: one open alert per `(product, alert_type)`. Severity escalation (e.g. high → critical) updates the alert and emits one `escalated` notification; repeated recalculations at the same severity emit nothing.
- Notification cooldown per product (default 24 h) except for escalation to `critical`.

### 10.8 Backtesting (required before any claim of predictive improvement)
Build a backtest harness (`scripts/run_backtest.py`, module `risk/backtest`):
- Replay history: for each product and each historical evaluation date `t`, compute the engine's output using **only data available before `t`**, then compare with whether a stock-out actually occurred within the next horizon (default 14 days).
- Reconstruct historical stock from the adjustment ledger, sales and receipts. Where stock history is not reconstructable, the product is excluded and counted.
- Baseline comparator: `days_of_cover < expected lead time` (the "stock divided by demand" rule).
- Report precision, recall, false-alert rate, median warning lead time, Brier score and a reliability table, for the engine vs the baseline, with the sample size and a plain statement of what it does and does not show.
- Run on **synthetic** data (labelled) to validate the harness and on **real** data only if it exists. Do not state or imply the engine outperforms the baseline unless the measured result shows it, on stated data.

---

## 11. CAUSAL LAYER SPECIFICATION

### 11.1 Principle
A causal library does not create causality. The graph below is a set of **documented domain assumptions**. It must (a) change the actual risk calculation, (b) be inspectable, and (c) carry an **evidence tier** for each edge. If you cannot justify an edge, do not include it.

### 11.2 Graph variables and edges (v1)
```
SeasonalEvent ──► DemandMultiplier (m) ──► DemandRate ──► StockDepletion ──► StockOut
VendorReliability ──► ArrivalDelay (δ) ──► ArrivalTime (A) ──► StockOut
FxDepreciation ──► ArrivalDelay (δ)        [only for vendors flagged imports_goods = true]
StockOnHand ──► StockDepletion
```
Three treatable factors: `seasonality`, `vendor_reliability`, `fx_rate`. The baseline stock position (stock vs demand vs nominal lead time) is a fourth, non-optional driver reported as `stock_position`.

### 11.3 Structural equations and evidence tiers
Each factor reports an **evidence tier**: `data_estimated`, `assumption_based`, or `insufficient`. Only the first two may contribute to a calculation; `insufficient` is shown as "monitored, not yet quantified".

- **Seasonality → demand multiplier `m`.** For each calendar event overlapping the forecast window, estimate the product's uplift from its **own history**: ratio of mean daily sales in the event's previous occurrence(s) to the pre-event baseline of equal length, **shrunk toward 1** by `n/(n+k)` (k default 2 occurrences). If the product has no covered history for a prior occurrence, `m = 1`, tier `insufficient`, and the UI shows "event upcoming, uplift unknown". Never insert hand-picked multipliers.
- **Vendor reliability → arrival delay `δ`.** Empirical lateness distribution from the business's own deliveries (tier `data_estimated` when `n_vendor ≥ 5`; else `insufficient`).
- **FX depreciation → arrival delay.** Applies only to vendors flagged `imports_goods`. Define `Δ30` = percentage depreciation of NGN against USD over the last 30 days (configurable window, rate type documented in Stage 8). Effect `δ_fx = β · max(0, Δ30)` days. `β` is **data_estimated** only if the workspace has enough completed orders with this vendor profile (default ≥ 15) and a documented regression of lateness on lagged `Δ30` passes a placebo/refutation test (e.g. shuffled-FX placebo; use `dowhy` refutation only if it is adopted and justified); otherwise it is **assumption_based** *only* if the owner explicitly set `β` in settings (UI states "your assumption"), otherwise `insufficient`. No default `β` is invented.

### 11.4 Contributions by intervention (exact Shapley over ≤ 3 factors)
For each subset `T` of the enabled, quantifiable factors, compute `risk(T)` = the engine's `P(stockout)` with factors in `T` at their actual values and the rest set to **neutral references**:
- seasonality neutral: `m = 1`
- vendor reliability neutral: `δ = 0` (on-time delivery at nominal lead time)
- fx neutral: `δ_fx = 0`

Contribution of factor `i` = Shapley value over all `2^n` subsets (n ≤ 3, so ≤ 8 evaluations). The contributions plus `risk(∅)` sum exactly to `risk(all)`. `risk(∅)` is reported as the `stock_position` driver. Present shares as a fraction of `risk(all)`; if `risk(all) < 0.05`, do not present shares.
Stale or insufficient factors are excluded from the subsets and shown with their reason.

### 11.5 Required behaviour
- Disabling a factor in settings changes the computation and the output.
- The engine records the DAG version, edge evidence tiers, and parameter values in `risk_snapshots.evidence` for audit and for the explanation input.
- `docs/RISK_ENGINE.md` contains the DAG, every assumption, and a "what this does not establish" section.
- Do not describe outputs as proven causes. UI copy uses "contributing factor" and states the evidence tier.

---

## 12. OPENAI EXPLANATION LAYER CONTRACT

### 12.1 Provider interface
```python
class ExplanationProvider(Protocol):
    async def explain(self, request: ExplanationRequest) -> ProviderResult: ...
```
Implementations: `OpenAIExplanationProvider` and `FallbackExplanationProvider` (deterministic templates, no network). The model id, API base, timeouts, retry policy, and prices per million tokens come from configuration (`OPENAI_MODEL`, `OPENAI_TIMEOUT_S`, `OPENAI_PRICE_INPUT_PER_M`, `OPENAI_PRICE_OUTPUT_PER_M`). **Do not hard-code a model name or price.** At implementation time, read the provider's current documentation for the structured-outputs request format and record the verified model id and date in `docs/DECISIONS.md`; if you cannot access the documentation or credentials, implement against the SDK's typed interface, mark live verification as pending, and continue.

### 12.2 Request (built by the backend only from the authoritative snapshot)
```json
{
  "schema_version": 1,
  "product_label": "this product",
  "risk": {"band": "high", "stockout_chance_pct": 65, "days_of_cover": 4.2,
           "expected_arrival_days": 7.0, "confidence": "medium"},
  "inventory": {"stock_on_hand": 100, "daily_demand": 23.8, "reorder_threshold": 60,
                "suggested_reorder_qty": 140},
  "factors": [
    {"id": "stock_position", "share_pct": 55, "evidence_tier": "data_estimated", "fresh": true},
    {"id": "vendor_reliability", "share_pct": 30, "evidence_tier": "data_estimated", "fresh": true},
    {"id": "seasonality", "share_pct": null, "evidence_tier": "insufficient", "fresh": true}
  ],
  "data_warnings": ["limited_vendor_history"],
  "allowed_actions": ["order_earlier", "check_backup_vendor", "review_stock_count", "monitor"]
}
```
All numbers originate from the snapshot. `stockout_chance_pct` is omitted when confidence is low. Factor ids are an enumerated set.

### 12.3 Privacy
Never send: user emails, workspace/company name, vendor names, customer data, or free-text notes. Product names are sent only if `AI_SEND_PRODUCT_NAMES=true` (default **false**; use `product_label`). Send only the fields needed. Document exactly what leaves the system in `docs/SECURITY.md`.

### 12.4 Response schema (strict structured output)
```json
{
  "summary": "string <= 200 chars",
  "factors": [{"id": "enum", "explanation": "string <= 240 chars"}],
  "explanation": "string <= 700 chars",
  "recommended_action": {"action": "enum from allowed_actions", "text": "string <= 300 chars"},
  "warnings": ["string <= 160 chars"]
}
```

### 12.5 Validation (all must pass or the response is rejected)
1. Parses against the strict schema; no extra fields.
2. Every `factors[].id` is in the request's factor ids; no invented factors; none for `insufficient` factors with a share.
3. **Numeric audit:** every number appearing in any generated text must match a value (allowing rounding and unit formatting) from the request's allowed numeric set; any other number → reject. Tests include adversarial outputs (invented percentages, dates, currency amounts, quantities).
4. `recommended_action.action` ∈ `allowed_actions`; text must not instruct an automatic purchase.
5. Low confidence responses must contain a data-quality warning (the backend injects it deterministically if missing).
6. Length limits and a simple prohibited-content check.

On rejection: one bounded retry with a corrective instruction; if still invalid, store the **fallback** explanation (`source = fallback`) and log the reason. Generated text never overrides backend numbers; the UI renders numbers from the snapshot next to the prose.

### 12.6 Caching, limits, cost
- `explanation.input_hash` = hash of the request payload. Reuse an explanation when the hash is unchanged. Generate a new one only when the band, rounded chance, factor shares (rounded to 5%), confidence, or warnings change materially. Never call the model during routine recalculation without a material change.
- Per-workspace monthly caps on tokens and estimated cost (`workspace_settings`, with environment defaults). Before a call, check the cap; if exceeded, use the fallback, increment `blocked_requests`, and show "AI explanations paused: usage limit reached" to the owner. Record usage after each call from the provider's reported token counts.
- Handle timeouts, 429s (exponential backoff with jitter, capped), 5xx, missing credentials (fallback + clear operator log), and network failure. A circuit breaker pauses calls for a cool-down after repeated failures.
- Explanations are generated by a background job, not in the request path.

---

## 13. EXTERNAL SIGNAL SPECIFICATIONS

### 13.1 Naira exchange rate
- Interface `FxRateProvider.get_rate(pair, on_date) -> FxObservation(rate, rate_type, observed_on, source, fetched_at)`.
- **Rate type matters.** Nigeria has had divergence between official and parallel-market rates. Record which type the provider returns, name it in the UI and docs, and never mix types in one series. Default to an official/interbank-type rate unless the owner configures otherwise; record the decision.
- Stage 8 requires you to **verify candidate sources with live calls** (test at least two candidates, record availability, rate type, update frequency, terms of use, rate limits, and cost). Do not assume any provider works. If no candidate is reachable or suitable, implement the interface, ship a clearly labelled manual-entry rate with a staleness warning, mark `fx_rate` auto-update as a **blocked external dependency**, and continue.
- Refresh job every 6 hours (configurable); store every observation with provenance; staleness threshold 48 h; failure behaviour: keep last good value, flag stale, exclude from contributions, show a banner on affected products.

### 13.2 Seasonality calendar
- Maintained as data (`seasonal_events` seed file in the repo, versioned), covering Nigerian public holidays and commercially relevant periods (e.g. Christmas/New Year, Easter, Eid al-Fitr and Eid al-Adha, Ramadan, school-resumption periods). Lunar-calendar events need dated occurrences per year: store concrete dates for at least the current and next two years and document how to extend them and their source. Do not invent dates; cite where each came from or mark `needs_verification`.
- The calendar identifies **which events overlap a window**. Demand uplift comes only from the product's own history (Section 11.3), never from the calendar itself.
- Provide a function `events_overlapping(start, end)` with boundary tests (inclusive/exclusive, year rollover, multi-day events).
