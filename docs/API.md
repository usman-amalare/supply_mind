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
