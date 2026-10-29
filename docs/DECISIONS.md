# Decisions

Status labels: **Accepted**, **Assumed**, **Unresolved**, **Blocked**.

Dates are the day the decision was recorded. This file does not claim that missing master-prompt sections were recovered.

## D-001 — Missing master-prompt sections

**Status:** Accepted (gap record). **Date:** 2026-10-29.

`SUPPLYMIND_MASTER_BUILD_PROMPT.md` is 443 lines and ends at Section 13.2 (seasonality calendar). These referenced parts are absent:

- Section 14, including the ledger format and Section 14.6 (blockers)
- Section 15, including Section 15.3 (reference oracle procedure)
- Section 16 (ordered stages)
- Appendix A (condensed PRD)

The product brief PDF in the repository root was read in full. It is five pages and is the product-scope source.

What still governs implementation is the text that is present: Sections 1–13, the product brief, and this ledger. The stage list in `IMPLEMENTATION_PLAN.md` is **reconstructed** from those sources and from the backend-first instruction for this repository. It is not a transcription of Section 16.

Section 10.4 already says the reference oracle uses the same stock-out formula computed independently. Section 10.8 already states the backtest metrics. Those statements stand. The missing Section 15.3 procedure is not reconstructed beyond them.

## D-002 — Conflict resolutions between the brief and the master prompt

**Status:** Accepted. **Date:** 2026-10-29.

| Topic | Product brief | Master prompt | Resolution |
|---|---|---|---|
| Onboarding order | Company, products, vendors, risk factors | Company, vendors, products, optional sales history, risk factors, finish | Follow master prompt Section 4.3. Products and vendors both stay in scope. The product form may create a vendor inline. |
| Causal libraries | Names pgmpy/dowhy | networkx plus structural equations; adopt dowhy or pgmpy only after a later evaluation shows verified value | Follow the master prompt. Neither library is installed. |
| Naira rate | "Free, reliable public APIs" and unattended updates as acceptance criteria | Verify at least two live candidates in the signals stage; otherwise ship manual entry and mark auto-update blocked | No provider is selected. `FX_PROVIDER=manual` is the only allowed value. The brief's unattended-update acceptance criterion is **unmet**. |
| Pilot | 3–5 businesses for 4 weeks | Do not fabricate pilot results | Not an engineering stage. **Blocked** on a real pilot. |
| Build order vs UI | Early foundation includes screens | This repository's instruction is backend first | API contracts and tests come before frontend screens. |
| Purchasing | Suggestions now; automatic purchasing is out of v1 | No code path may purchase or send a purchase order | Aligned. Not built. |
| Public API product | Later, not a v1 priority | Explicit non-goal | Aligned. Not built. |

## D-003 — Working blocker rule

**Status:** Assumed substitute for missing Section 14.6. **Date:** 2026-10-29.

Stop and report when continuing would invent product behaviour, claim an unverified external integration works, or a required local dependency cannot be started. Record other engineering choices here and continue. This paragraph is not the text of Section 14.6.

## D-004 — UUID primary keys

**Status:** Accepted. **Date:** 2026-10-29.

Primary keys are UUID4 from the Python 3.12 standard library (`uuid.uuid7` is not available in 3.12). The master prompt allows UUID4 or UUID7. No extra UUID package is added. `supplymind.core.ids.new_id` is the only generator so a later UUID7 swap has one call site.

## D-005 — Quantities are fractional

**Status:** Accepted. **Date:** 2026-10-29.

Quantities use `NUMERIC(14,3)`. Money uses `NUMERIC(14,2)` plus a currency code. Section 7 gives these types and says integers would require a later stage decision. That stage text is missing, so the written default stands. Fractional goods remain representable.

## D-006 — Global rows versus tenant rows

**Status:** Accepted. **Date:** 2026-10-29.

`fx_rates` and `seasonal_events` have no `workspace_id`, matching Section 8.1.

`jobs.workspace_id` is nullable because an exchange-rate refresh is global. Tenant jobs must set `workspace_id`. Dedupe keys are globally unique among pending and running jobs, so a later job producer must include the workspace id in tenant dedupe keys.

`audit_log.workspace_id` is nullable. Section 9 requires sign-in and password-reset audit events, including attempts that have no workspace (unknown email, or a user row that does not yet have a membership). Workspace APIs must not return rows whose `workspace_id` is null. This is a deliberate exception to "tenant tables are NOT NULL".

## D-007 — Enumerations and names that the schema had to choose

**Status:** Assumed where noted. **Date:** 2026-10-29.

Stored as strings with database checks when the value set is stated in Sections 4.3, 8, or 10:

- Onboarding steps: `company`, `vendors`, `products`, `sales_history`, `risk_factors`, `finish`
- Membership role: `owner` only. A partial unique index allows one owner per workspace. Future roles can be added without allowing two owners.
- Product-vendor roles: `primary`, `backup`. At most one of each per product. The single backup follows the brief's singular "backup vendor". The same vendor cannot be linked twice, so the backup cannot equal the primary.
- Stock-adjustment reasons: the six values in Section 8.1
- CSV import and row statuses: the values in Section 8.1
- Order statuses: `open`, `delivered`, `cancelled`. A delivered order must have `actual_delivery_date`, and a non-delivered order must not.
- Alert statuses: `open`, `acknowledged`, `resolved`, `auto_resolved` (Section 10.7)
- Alert types: **Assumed** names `stockout_risk` and `reorder_point_reached`. The second string is the event named in Section 10.4. The first names the probability alert, which the prompt does not give a literal string.
- Risk bands and alert severity: `low`, `medium`, `high`, `critical`
- Confidence: `low`, `medium`, `high`
- Explanation source: `ai`, `fallback`
- Notification events: `opened`, `escalated`
- Job statuses: **Assumed** `pending`, `running`, `succeeded`, `failed`. The partial unique index names the first two. Terminal states are required for `attempts` and `last_error` to have an end.

Not checked in the database yet, because the allowed sets are not specified:

- `csv_imports.duplicate_policy`
- `csv_imports.date_format`
- `workspaces.size_band`
- `notifications.status`
- `fx_rates.rate_type` and `workspace_settings.fx_rate_type`
- `vendors` contact columns are **Assumed** as `contact_name`, `contact_email`, and `contact_phone`

`products.sku` uniqueness is `(workspace_id, lower(sku))` for every row, including archived products. Archived SKUs stay reserved.

Sales coverage may be more than one row per product. Overlap prevention is not a database constraint yet (**Unresolved**).

`fx_rates.pair` is constrained to `USD/NGN` for v1.

## D-008 — Workspace settings defaults

**Status:** Accepted, with one unresolved field. **Date:** 2026-10-29.

- Enabled risk factors default to an empty list. Stock position remains a non-optional driver in the engine spec; the three selectable factors start off until the business chooses them.
- Alert thresholds default to the Section 10.4 edges: medium `0.25`, high `0.50`, critical `0.80`, plus resolve hysteresis `0.05` from Section 10.7. These are configuration defaults, not calibrated truth.
- Notification cooldown defaults to 24 hours. Recipient emails start empty.
- Risk recalculation interval defaults to 60 minutes on the workspace, not as a second environment variable.
- `ai_monthly_token_cap` and `ai_monthly_cost_cap` are null. No cap number exists in either document (**Unresolved**). Null means live explanation calls stay disabled.
- `fx_delay_beta` is null and has no default. Section 11.3 forbids inventing β.
- `fx_rate_type` on the workspace is null until a rate type is verified and the owner chooses one. Observations store their own `rate_type`. Do not mix types in one series.

Lookback (56 days), demand half-life (14 days), and safety days (3) stay as future engine constants from Section 10. They are not columns yet.

## D-009 — Security defaults that the prompt requires to be configurable

**Status:** Assumed durations and names. **Date:** 2026-10-29.

The prompt requires server-side sessions, configurable absolute and idle timeouts, an HttpOnly cookie, `SameSite=Lax`, a CSRF header, and Argon2id. It does not state the timeout values or the cookie name.

- Absolute timeout: 12 hours
- Idle timeout: 1 hour
- Cookie name: `supplymind_session`
- CSRF header name: `X-CSRF-Token`
- Password length: 10 to 128 characters. The minimum is specified. The maximum is an operational limit so hashing cannot be fed an unbounded payload. A breach-list check is optional in the prompt and is not implemented.
- Application secrets must be at least 32 characters and must not be a known placeholder. Production also requires `SESSION_COOKIE_SECURE=true`, at least one `https://` frontend origin, and rejection of the local example database credential pair.
- Session tokens and reset tokens are stored only as SHA-256 hashes. Client IP addresses are stored only as HMAC-SHA256 using the application secret. Raw IPs are not stored.
- CSRF route enforcement is not active yet. The compare and hashing helpers exist. Wiring them to mutating routes is part of identity.
- In-process rate limiting is the v1 mechanism from Section 5. It does not coordinate across processes. No Redis limiter is added.
- `/docs` and `/openapi.json` are disabled when `APP_ENV=production`.

## D-010 — Configuration names

**Status:** Mixed. **Date:** 2026-10-29.

Names stated by the master prompt are used as stated: `DATABASE_URL`, `APP_ENV`, `OPENAI_MODEL`, `OPENAI_TIMEOUT_S`, `OPENAI_PRICE_INPUT_PER_M`, `OPENAI_PRICE_OUTPUT_PER_M`, `AI_SEND_PRODUCT_NAMES`.

`OPENAI_API_KEY` is the official SDK environment name for a credential the prompt requires the server to hold. It is not a hardcoded model or price.

These names are **Assumed** and documented in `.env.example`: `APP_SECRET`, `LOG_LEVEL`, `FRONTEND_ORIGINS`, session variables, `CSRF_HEADER_NAME`, AI cap variables, `CSV_MAX_BYTES`, `CSV_MAX_ROWS`, `FX_PROVIDER`, `FX_STALENESS_HOURS`, `FX_REFRESH_INTERVAL_HOURS`, and the `SMTP_*` variables.

`OPENAI_TIMEOUT_S` defaults to 30 seconds (**Assumed**). Model id and both prices default to unset. `AI_SEND_PRODUCT_NAMES` defaults to false, which is specified.

CSV limits default to 5 MB and 50,000 rows, which are specified. FX staleness defaults to 48 hours and refresh to 6 hours, which are specified. `FX_PROVIDER` accepts only `manual`.

SMTP is not required for process startup. Email is not implemented. Missing SMTP must surface as an explicit notification failure later, not as a pretended send.

## D-011 — Build backend and dependency timing

**Status:** Accepted. **Date:** 2026-10-29.

`uv` 0.11 scaffolds `uv_build`. This project uses that backend instead of adding hatchling. Python is constrained to `>=3.12,<3.13` because 3.12 is the locked runtime and newer versions are not tested.

Libraries are added in the stage that uses them. The platform stage does not install numpy, scipy, pandas, networkx, dowhy, pgmpy, the OpenAI SDK, or respx. `freezegun` is installed because the clock test uses it.

The initial Alembic revision creates tables from SQLAlchemy metadata and then adds append-only triggers. A test compares database metadata with the models after upgrade. Later schema changes must be new revisions. Do not edit `0001_initial_schema` after it has been applied outside a disposable database.

`stock_adjustments` and `audit_log` reject `UPDATE` and `DELETE` with triggers. `TRUNCATE` by the table owner is not blocked. No `ON DELETE CASCADE` foreign keys are used.

ORM `relationship()` attributes are deferred until the module that queries them is built. Foreign keys are already in the schema.

## D-012 — Local tooling gaps

**Status:** Accepted. **Date:** 2026-10-29.

GNU `make` is not installed on the development machine used for the foundation stage. `Makefile` is still the command contract, and CI calls it. Local verification runs the same commands directly and says so in the ledger.

Docker Desktop was installed and the engine service was stopped at inspection. Integration tests need PostgreSQL 16. If the daemon cannot be started, schema tests are **Blocked**, not skipped.

The tracked product README is `readme.Md`. On Windows that path is the repository README. It is updated in place and is not replaced.

## D-013 — Health routes

**Status:** Assumed names. **Date:** 2026-10-29.

`GET /health` is liveness and does not touch the database. `GET /ready` runs `SELECT 1` and returns 503 with `{"status": "unavailable"}` on failure, without returning the exception text. These are operational probes, not `/api/v1` product resources.

## D-014 — Frontend and deployment are not started

**Status:** Accepted. **Date:** 2026-10-29.

`frontend/` contains only the target directories and a status note. No React application, lockfile, or screens exist.

`deploy/dev` and `deploy/test` compose files start PostgreSQL 16. The dev file also starts Mailpit. `deploy/prod` is a status note. Caddy, backups, and a production image are **Proposed**, not written and not deployed.

## D-015 — Synchronous database sessions

**Status:** Accepted. **Date:** 2026-10-29.

The platform uses a synchronous SQLAlchemy engine and `Session`. Database handlers will be synchronous FastAPI functions so the event loop is not blocked. psycopg can do async I/O later without a migration if that becomes necessary. The schema does not depend on this choice.

## D-016 — Readable initial migration

**Status:** Accepted. **Date:** 2026-10-29.

Revision `0001_initial_schema` creates tables with `Base.metadata.create_all` and then installs append-only triggers in explicit SQL. The schema test fails if reflected metadata drifts from the models. A later change is a new revision. This revision stays as is once any non-disposable database has applied it. It was chosen so the migration cannot list a different shape from the models. The table list is still visible in `modules/*/models.py`.
