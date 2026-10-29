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
- CSRF route enforcement is active as of Stage 2. See D-017. The earlier sentence that it was not wired is historical.
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

## D-017 — Stage 2 identity, sessions, and workspace context

**Status:** Accepted, with assumed values marked below. **Date:** 2026-10-29.

Stage 2 keeps the synchronous SQLAlchemy session from D-015. The stage prompt's mention of an async engine is not followed; converting the working engine would be a new architecture.

Registration creates the user, workspace (`Africa/Lagos`, `NGN`, onboarding step `company`), owner membership, and workspace settings in one transaction, then a server session. The response sets the session cookie and returns a CSRF token. A failed registration rolls the transaction back. Duplicate emails, including case variants, return `409` with a message that does not say the email is taken. The status code still differs from success, so a caller can observe that the details were rejected.

Login returns the same `401` body for an unknown email, a wrong password, an inactive user, a malformed password hash, and a user with no single owner membership. Unknown and inactive accounts run a dummy Argon2 verification. Login revokes only the session cookie that was presented, then issues a new one. Other devices stay signed in until `POST /api/v1/auth/sessions/revoke`.

Sessions store SHA-256 token and CSRF hashes. Idle timeout uses `last_seen_at` and the injected clock. Absolute timeout uses `expires_at` set at creation and is not extended by activity. Cookies are `HttpOnly`, `SameSite` from settings (default `lax`), `Path=/`, no `Domain`, and `Secure` only when `SESSION_COOKIE_SECURE` is true. Production still refuses to start unless that flag is true.

CSRF is required on unsafe methods for cookie-authenticated routes. `require_csrf` compares the configured header with the session's CSRF hash. `GET /api/v1/auth/csrf` rotates that secret. These routes are the only unsafe exceptions, because they have no session-bound token yet: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/password-resets`, and `POST /api/v1/auth/password-resets/confirm`. A unit test fails if another unsafe `/api/v1` route is neither exempt nor protected.

The workspace id comes from the session user's single owner membership. Zero memberships, or more than one, fail closed with `403`. Client `workspace_id` fields are rejected on write models (`extra=forbid`). Query parameters are not read. Workspace settings in this stage expose notification recipients and cooldown only. Risk-engine fields stay at schema defaults and are not in the API.

Password reset stores a single-use SHA-256 token for `PASSWORD_RESET_TTL_MINUTES` (default 30, assumed). The HTTP request always returns `204` and never returns the token. Email delivery is not implemented; Stage 13 owns SMTP. Until then a person cannot receive a reset token. Confirm revokes every session for that user. Email verification is not implemented. `email_verified_at` stays null, and later notification code must not treat an account as verified.

Signup, login, and password reset use the existing in-process limiter. Defaults are 20 attempts per 10 minutes per socket address, separate buckets (assumed). The limiter does not cross processes. The client address is `request.client.host`, not `X-Forwarded-For`.

Argon2id parameters are settings. Defaults are the library's RFC 9106 low-memory profile: time cost 3, memory 65536 KiB, parallelism 4. Tests lower the cost so the suite can finish; production defaults stay at that profile. No breach-list check is called.

Account tables are not tenant tables. `AccountRepository` and `AuditRepository.append` do not take a `TenantContext`. `create_owner_workspace` creates the tenant and does not accept a client workspace id. Later workspace reads and updates go through `WorkspaceRepository`, which requires `TenantContext`. No migration was added. `0001_initial_schema` was not edited.

Application-layer tenancy is not PostgreSQL row-level security. The full Section 9 isolation suite for products, vendors, orders, imports, sales, alerts, snapshots, explanations, usage, and notifications is a gate for the stages that add those routes. A test already fails if a new non-auth `/api/v1` route has no isolation entry. Settings are covered now.

Email shape is assumed: trimmed, casefolded, one `@`, and a dotted domain. Notification cooldown is 1–168 hours. At most 20 recipient emails are stored. Those bounds are not in the master prompt.
