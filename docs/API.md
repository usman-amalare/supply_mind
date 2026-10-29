# API

Stage 2 exposes identity and the current workspace. Later resources are not implemented. Paths are under `/api/v1`. JSON only.

Errors use `{ "error": { "code", "message", "details"?, "request_id" } }`. `details` is omitted when there is nothing useful to add. Responses do not include stack traces, SQL, password hashes, or session tokens.

`/docs` and `/openapi.json` are available outside production and disabled when `APP_ENV=production`.

## Session cookie

Name: `SESSION_COOKIE_NAME` (default `supplymind_session`).

- `HttpOnly`
- `SameSite` from `SESSION_COOKIE_SAMESITE` (default `lax`)
- `Secure` when `SESSION_COOKIE_SECURE` is true. Production refuses to start otherwise.
- `Path=/`
- No `Domain`
- `Max-Age` is the absolute timeout in seconds

The raw session token is not in JSON, logs, or the URL. The database stores SHA-256 hashes of the session token and the CSRF token.

Absolute lifetime is `SESSION_ABSOLUTE_TIMEOUT_HOURS` (default 12) from creation. It does not move when the session is used. Idle lifetime is `SESSION_IDLE_TIMEOUT_HOURS` (default 1) since `last_seen_at`. Both use the application clock.

Login revokes the session cookie presented with that login and sets a new cookie. Other devices remain signed in until revoke-all.

## CSRF

Header: `CSRF_HEADER_NAME` (default `X-CSRF-Token`).

Registration and login return `csrf_token` once. `GET /api/v1/auth/csrf` rotates it; the previous value stops working. Unsafe methods on cookie-authenticated routes require the header. The session cookie is not accepted in place of the header.

Unauthenticated exceptions, because they have no session-bound token yet:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/password-resets`
- `POST /api/v1/auth/password-resets/confirm`

## CORS

`FRONTEND_ORIGINS` is a comma-separated allowlist. A wildcard is rejected. Credentialed requests are allowed only for listed origins. Production requires `https://` origins.

## Rate limits

Signup, login, and password reset are limited in-process per socket address. Defaults: `AUTH_RATE_LIMIT_ATTEMPTS=20` per `AUTH_RATE_LIMIT_WINDOW_SECONDS=600`, in separate buckets. A second API process would not share counters. `429` uses code `rate_limited`.

## Auth

### `POST /api/v1/auth/register`

Body: `email`, `password` (10–128 characters), `workspace_name`. Unknown fields, including `workspace_id`, are rejected.

`201` returns `user` (`id`, `email`), `workspace` (id, name, industry, size_band, timezone, currency, onboarding_step, onboarding_completed_at), and `csrf_token`. Sets the session cookie.

The email is trimmed and lowercased. The workspace is created with timezone `Africa/Lagos`, currency `NGN`, and onboarding step `company`, plus an owner membership and a settings row. Password hashes are Argon2id.

`409` `registration_conflict` when the email is already registered, including a different case. `422` when the body is invalid. Neither response contains the password or a hash.

### `POST /api/v1/auth/login`

Body: `email`, `password`. `200` has the same shape as registration and sets a new cookie.

`401` `invalid_credentials` with the message `Email or password is incorrect.` for an unknown email, a wrong password, an inactive user, a malformed stored hash, and a user without exactly one owner membership.

### `POST /api/v1/auth/logout`

Requires the session cookie and CSRF header. Revokes that session, then clears the cookie. `204` only after the revoke is committed.

### `POST /api/v1/auth/sessions/revoke`

Requires the session cookie and CSRF header. Revokes every active session for the user, then clears the cookie. `204` only after the update is committed. Previously issued cookies then fail.

### `GET /api/v1/auth/me`

Requires the session cookie. Returns `id` and `email`.

### `GET /api/v1/auth/csrf`

Requires the session cookie. Returns a new `csrf_token` and invalidates the previous one.

### `POST /api/v1/auth/password-resets`

Body: `email`. Always `204` with an empty body, whether or not the email exists. A hashed single-use token is stored for `PASSWORD_RESET_TTL_MINUTES` (default 30) when the account is active. The token is not returned and email is not sent. A person cannot complete reset until mail delivery exists.

### `POST /api/v1/auth/password-resets/confirm`

Body: `token`, `password`. `204` on success: the password is replaced, the token is spent, and every session for that user is revoked. Unknown, expired, and already-used tokens return `400` `reset_rejected` with the same message.

## Workspace

The workspace is the one owned by the session. These routes do not take a workspace id.

### `GET /api/v1/workspace`

Returns the session workspace. A `workspace_id` query parameter is ignored.

### `PATCH /api/v1/workspace`

Body: `name`. Requires CSRF. Extra fields are rejected.

### `GET /api/v1/workspace/settings`

Returns `notification_prefs.recipient_emails` and `notification_prefs.cooldown_hours` only. Alert thresholds, risk factors, AI caps, and FX fields are not in this response.

### `PATCH /api/v1/workspace/settings`

Body: `notification_prefs` with `recipient_emails` (at most 20) and `cooldown_hours` (1–168). Requires CSRF. Replaces those two fields. Other settings columns are left unchanged.

Missing settings for the caller's own workspace return `404` `not_found`. Another workspace's settings are not addressable on these routes.

A session whose user has no membership, or more than one, receives `403` `workspace_unavailable`.

## Catalog

All catalog routes require the session cookie. Mutations require the CSRF header. Every query and write is scoped to the session workspace. A client `workspace_id` is rejected on write bodies (`extra=forbid`) and is not used as a filter. Another workspace's id returns `404` `not_found`.

List responses use `{items, page, page_size, total}`. Default `page=1`, `page_size=20`, maximum `page_size=100`. Ordering is by name then id for vendors, and by sku then id for products. Optional `q` searches name/contact (vendors) or sku/name (products). Optional `include_archived=true` includes soft-archived rows; the default is active rows only. `GET` by id still returns an archived row in the caller's workspace.

### Vendors

#### `POST /api/v1/vendors`

Body: `name`, optional `contact_name`, `contact_email`, `contact_phone`, `typical_lead_time_days` (0–3650), `imports_goods` (default false). `201` returns the vendor view.

#### `GET /api/v1/vendors`

Paginated list. Query: `page`, `page_size`, `include_archived`, `q`.

#### `GET /api/v1/vendors/{vendor_id}`

Returns one vendor, including when archived.

#### `PATCH /api/v1/vendors/{vendor_id}`

Updates allowed fields on an active vendor. Archived vendors return `404`.

#### `POST /api/v1/vendors/{vendor_id}/archive`

Sets `archived_at`. Idempotent if already archived. `409` `vendor_in_use` when the vendor is still primary or backup for any active product. Relationships are not deleted. There is no restore endpoint in this stage.

### Products

#### `POST /api/v1/products`

Body: `sku`, `name`, `unit`, `reorder_threshold` (≥ 0), optional `current_stock` (default 0), optional `unit_cost` with `unit_cost_currency` (both required together). `201` returns the product. `409` `sku_conflict` when `lower(sku)` already exists in the workspace, including for archived products.

`current_stock` may be set only on create. Create always writes one `stock_adjustments` row with reason `initial` in the same transaction: `delta` and `balance_after` equal the opening quantity (including explicit or default zero). A failed ledger insert rolls back the product.

#### `GET /api/v1/products`

Paginated list. Query: `page`, `page_size`, `include_archived`, `q`.

#### `GET /api/v1/products/{product_id}`

Returns one product, including when archived.

#### `PATCH /api/v1/products/{product_id}`

Updates `sku`, `name`, `unit`, `reorder_threshold`, and unit cost fields on an active product. `current_stock` is rejected. `clear_unit_cost: true` clears both cost fields. `409` `sku_conflict` on a case-insensitive clash.

#### `POST /api/v1/products/{product_id}/archive`

Sets `archived_at`. Idempotent if already archived. Product–vendor links remain. There is no restore endpoint in this stage.

### Product vendors

Roles are path values `primary` or `backup`. At most one of each per product. The same vendor cannot hold both roles.

#### `GET /api/v1/products/{product_id}/vendors`

Returns the product's links with `vendor_name` and `vendor_archived_at`.

#### `PUT /api/v1/products/{product_id}/vendors/{role}`

Body: `vendor_id`. Assigns or replaces that role. Replacing primary removes the previous primary first. The same vendor already in that role is a no-op success. `409` `vendor_role_conflict` when that vendor already holds the other role. `409` `product_vendor_conflict` when a uniqueness constraint fails (including concurrent primary assignment). The vendor and product must be active and in the session workspace.

#### `DELETE /api/v1/products/{product_id}/vendors/{role}`

Removes that role. `204`. Missing role returns `404`.

### Stock ledger

Quantities use `NUMERIC(14,3)`. Actor, workspace, and `balance_after` are server-derived. There is no update or delete endpoint for ledger rows. Corrections are new rows with reason `correction`.

Allowed public adjustment reasons: `receipt`, `sale_deduction`, `damage`, `correction`, `manual_count`. Reason `initial` is reserved for product create and the Stage 4 baseline backfill.

Sign rules: `receipt` requires a positive delta; `sale_deduction` and `damage` require a negative delta; `correction` and `manual_count` accept either sign. Zero deltas are rejected. An adjustment that would leave `current_stock` below zero returns `409` `insufficient_stock`. Archived products return `404` (same non-disclosing shape as a missing product).

`source_ref` is optional free text (max 200). This endpoint does not treat it as an idempotency key. Duplicate `initial` rows are blocked by a partial unique index.

#### `POST /api/v1/products/{product_id}/stock-adjustments`

Authenticated + CSRF. Body: `delta`, `reason`, optional `note` (max 2000), optional `source_ref`. `201` returns the committed adjustment (`id`, `product_id`, `delta`, `reason`, `note`, `actor_user_id`, `balance_after`, `source_ref`, `created_at`). Locks the product row, updates `products.current_stock`, appends one ledger row, and writes audit action `stock_adjusted` in one transaction.

Errors: `404` `not_found`; `409` `insufficient_stock` / `ledger_uninitialized` / `ledger_conflict`; `422` `validation_error` / `invalid_adjustment`.

#### `GET /api/v1/products/{product_id}/stock-adjustments`

Authenticated. Paginated newest-first (`created_at` desc, `id` desc). Query: `page`, `page_size` (max 100), optional `reason`. Envelope `{items, page, page_size, total}`.

#### `GET /api/v1/products/{product_id}/stock`

Authenticated. Returns `{product_id, current_stock, ledger_status, latest_balance_after}`. `ledger_status` is `ok` when the latest ledger `balance_after` matches `current_stock`, `uninitialized` when there are no ledger rows, or `mismatch` when they disagree. This endpoint never rewrites stock or the ledger.
