# Security

This file records the controls that are implemented and the limits that are not. It is not a claim that the product has finished Section 9.

## Authentication

Passwords are hashed with Argon2id through `argon2-cffi`. Parameters come from `ARGON2_TIME_COST`, `ARGON2_MEMORY_COST`, and `ARGON2_PARALLELISM`. Defaults are the library's RFC 9106 low-memory profile (time 3, 64 MiB, parallelism 4). There is no custom hash and no breach-list lookup.

The minimum length is 10 characters, from the master prompt. The maximum is 128 so a request cannot submit an unbounded password. Stored hashes and raw session tokens are not returned and are not written to logs.

Login uses one error for unknown accounts, wrong passwords, inactive users, and unusable password hashes. Unknown and inactive lookups pay for a dummy Argon2 verification. A corrupt hash returns the same error and does not raise.

## Sessions

Sessions live in PostgreSQL. The cookie value and the CSRF value are stored only as SHA-256 hashes. Logout revokes the current row. Revoke-all sets `revoked_at` on every active row for that user before the handler returns success.

Expired, revoked, missing, and malformed cookies are rejected. Idle and absolute timeouts are the settings in `.env.example`. Tests move an injected clock instead of sleeping.

Production cookies are `Secure`. Development and test may set `SESSION_COOKIE_SECURE=false` for HTTP. Production startup rejects that.

## CSRF and CORS

Mutating cookie-authenticated `/api/v1` routes require `X-CSRF-Token` (or the configured header name). The comparison uses the hash stored on that session. A token from another session does not work. Calling `GET /api/v1/auth/csrf` replaces the current token.

Register, login, and the two password-reset posts do not require a CSRF header. They are the routes that create or recover a credential. A cross-site login that causes the browser to store a new cookie is a residual risk of that exception; `SameSite=Lax` blocks the cookie from being sent on a cross-site POST.

CORS allows only origins listed in `FRONTEND_ORIGINS`, with credentials. `*` is rejected at startup.

## Tenancy

A workspace is the tenant. The id is loaded from the authenticated user's owner membership. It is not taken from a body, query, header, or path.

`WorkspaceRepository` refuses to construct without a `TenantContext` and queries only that workspace. Users, sessions, and password-reset tokens are account records, not tenant records. Creating the first workspace cannot take a tenant id that does not exist yet; that insert does not accept a client id.

A user with no membership, or with more than one, is denied. Settings for the caller's workspace are the only settings these routes can read or change. This is application-layer tenancy. PostgreSQL row-level security is not enabled.

Section 9 also requires an isolation test for every later resource type: products, vendors, orders, imports, sales, alerts, snapshots, explanations, usage, and notifications. Those routes do not exist yet. `tests/unit/test_auth_routes.py` fails if a new `/api/v1` route outside `/api/v1/auth/` has no named isolation test. That suite is a gate for the stage that adds the route, not a claim that those resources were tested in Stage 2.

## Password reset and email

Reset tokens are single-use, hashed, and short-lived. The request response is empty for every email. The confirm error is the same for an unknown, expired, or used token.

No email is sent. The token is returned only to a delivery method the HTTP layer does not call. Reset cannot be completed by a user until the notification stage sends mail. `email_verified_at` is not set. Notifications must not treat an address as verified.

## Audit

Sign-in, logout, revoke-all, registration, password reset, and the Stage 2 settings changes append to `audit_log`. Failed login rows do not store the submitted email or password. The audit table is append-only for `UPDATE` and `DELETE`. `TRUNCATE` by the table owner is still not blocked.

## Rate limiting and addresses

The limiter is in-memory and per process. It is applied to signup, login, and password reset. CSV upload and model calls are not routes yet. The key uses the socket address, which is wrong behind a proxy until the proxy is configured to pass a trusted client address. `X-Forwarded-For` is not trusted.

## Headers

Responses set `X-Content-Type-Options`, `Referrer-Policy`, and a restrictive `Content-Security-Policy`. `Strict-Transport-Security` is set when `APP_ENV=production`. Caddy is not configured; that remains a later deployment task.
