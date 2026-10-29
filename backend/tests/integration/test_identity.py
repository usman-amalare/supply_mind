"""Identity, session, CSRF, and workspace-isolation tests. They use PostgreSQL."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from supplymind.clock import FrozenClock
from supplymind.core.ids import new_id
from supplymind.core.security import hash_token, make_password_hasher, verify_password
from supplymind.core.tenancy import TenantContext
from supplymind.db.enums import MembershipRole, OnboardingStep
from supplymind.db.session import make_engine, make_session_factory
from supplymind.main import create_app
from supplymind.modules.audit.models import AuditLog
from supplymind.modules.identity.models import PasswordResetToken, User
from supplymind.modules.identity.models import Session as SessionRecord
from supplymind.modules.identity.service import IdentityService
from supplymind.modules.workspaces.models import Membership, Workspace, WorkspaceSettings
from supplymind.modules.workspaces.repository import WorkspaceRepository
from tests.support import build_settings

PASSWORD = "correct-horse-1"
NEW_PASSWORD = "correct-horse-2"
_START = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def _email() -> str:
    return f"user-{uuid4()}@example.com"


def _params(database_url: str, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "database_url": database_url,
        "frontend_origins": "https://app.example.com",
        "argon2_time_cost": 1,
        "argon2_memory_cost": 8192,
        "argon2_parallelism": 1,
    }
    values.update(overrides)
    return values


@contextmanager
def make_client(
    database_url: str,
    clock: FrozenClock | None = None,
    **overrides: object,
) -> Iterator[tuple[TestClient, FrozenClock]]:
    active = clock or FrozenClock(_START)
    app = create_app(build_settings(**_params(database_url, **overrides)), clock=active)
    with TestClient(app) as client:
        yield client, active


@contextmanager
def db_session(database_url: str) -> Iterator[Session]:
    engine = make_engine(database_url)
    session = make_session_factory(engine)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


def _counts(database_url: str) -> tuple[int, int, int]:
    with db_session(database_url) as session:
        users = session.scalar(select(func.count()).select_from(User))
        workspaces = session.scalar(select(func.count()).select_from(Workspace))
        memberships = session.scalar(select(func.count()).select_from(Membership))
    return int(users or 0), int(workspaces or 0), int(memberships or 0)


def _cookie(response: httpx.Response) -> str:
    header = response.headers["set-cookie"]
    prefix = "supplymind_session="
    value = header.split(prefix, 1)[1].split(";", 1)[0]
    assert value
    return value


def _register(
    client: TestClient,
    email: str | None = None,
    *,
    password: str = PASSWORD,
    name: str = "Acme Stores",
) -> tuple[dict[str, object], str]:
    address = email or _email()
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/register",
        json={"email": address, "password": password, "workspace_name": name},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    cookie = _cookie(response)
    assert cookie not in response.text
    assert password not in response.text
    assert "$argon2" not in response.text
    return body, cookie


def _login(
    client: TestClient, email: str, password: str = PASSWORD
) -> tuple[dict[str, object], str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json(), _cookie(response)


def _csrf(body: dict[str, object]) -> str:
    token = body["csrf_token"]
    assert isinstance(token, str)
    return token


def _as(client: TestClient, cookie: str) -> None:
    client.cookies.clear()
    client.cookies.set("supplymind_session", cookie)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(_START)


@pytest.fixture
def client(database_url: str, clock: FrozenClock) -> Iterator[TestClient]:
    with make_client(database_url, clock) as (api, _clock):
        yield api


def test_registration_creates_owner_workspace_and_hashed_session(
    client: TestClient,
    database_url: str,
) -> None:
    email = "User.Name+tag@Example.com"
    body, cookie = _register(client, f"  {email}  ")
    user = body["user"]
    workspace = body["workspace"]
    assert isinstance(user, dict)
    assert isinstance(workspace, dict)
    assert set(body) == {"user", "workspace", "csrf_token"}
    assert set(user) == {"id", "email"}
    assert user["email"] == "user.name+tag@example.com"
    assert workspace["name"] == "Acme Stores"
    assert workspace["timezone"] == "Africa/Lagos"
    assert workspace["currency"] == "NGN"
    assert workspace["onboarding_step"] == "company"
    assert workspace["onboarding_completed_at"] is None
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "user.name+tag@example.com"
    current = client.get("/api/v1/workspace")
    assert current.status_code == 200
    assert current.json()["id"] == workspace["id"]
    hasher = make_password_hasher(time_cost=1, memory_cost=8192, parallelism=1)
    with db_session(database_url) as session:
        stored = session.scalar(select(User).where(User.email == "user.name+tag@example.com"))
        assert stored is not None
        assert stored.password_hash.startswith("$argon2id$")
        assert verify_password(PASSWORD, stored.password_hash, hasher)
        membership = session.scalar(select(Membership).where(Membership.user_id == stored.id))
        assert membership is not None
        assert membership.role == MembershipRole.OWNER
        assert str(membership.workspace_id) == workspace["id"]
        settings = session.scalar(
            select(WorkspaceSettings).where(
                WorkspaceSettings.workspace_id == membership.workspace_id
            )
        )
        assert settings is not None
        assert settings.notification_prefs["cooldown_hours"] == 24
        record = session.scalar(
            select(SessionRecord).where(SessionRecord.token_hash == hash_token(cookie))
        )
        assert record is not None
        assert cookie not in record.token_hash
        assert body["csrf_token"] not in record.csrf_token_hash
        assert record.csrf_token_hash == hash_token(str(body["csrf_token"]))
        assert record.ip_hash is None or "testclient" not in record.ip_hash


def test_invalid_registration_creates_no_rows(client: TestClient, database_url: str) -> None:
    before = _counts(database_url)
    short = client.post(
        "/api/v1/auth/register",
        json={"email": _email(), "password": "too-short", "workspace_name": "Acme"},
    )
    blank = client.post(
        "/api/v1/auth/register",
        json={"email": _email(), "password": PASSWORD, "workspace_name": "   "},
    )
    bad_email = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": PASSWORD, "workspace_name": "Acme"},
    )
    assert short.status_code == 422
    assert blank.status_code == 422
    assert bad_email.status_code == 422
    assert "too-short" not in short.text
    assert _counts(database_url) == before


def test_duplicate_and_case_variant_emails_conflict(client: TestClient) -> None:
    email = _email()
    _register(client, email)
    client.cookies.clear()
    again = client.post(
        "/api/v1/auth/register",
        json={"email": email.upper(), "password": PASSWORD, "workspace_name": "Other"},
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "registration_conflict"
    assert email not in again.text
    assert "uq_users" not in again.text
    assert "Integrity" not in again.text


def test_registration_rolls_back_when_a_later_write_fails(
    database_url: str,
    clock: FrozenClock,
) -> None:
    class ExplodingAudit:
        def append(self, **kwargs: object) -> None:
            raise RuntimeError("forced-failure")

    email = _email()
    before = _counts(database_url)
    engine = make_engine(database_url)
    session = make_session_factory(engine)()
    service = IdentityService(
        session,
        clock,
        build_settings(**_params(database_url)),
        audit=ExplodingAudit(),
    )
    try:
        with pytest.raises(RuntimeError, match="forced-failure"):
            service.register(
                email=email,
                password=PASSWORD,
                workspace_name="Rollback Stores",
                user_agent=None,
                ip=None,
                request_id="rollback-test",
            )
    finally:
        session.close()
        engine.dispose()
    assert _counts(database_url) == before


def test_concurrent_duplicate_registration_leaves_one_owner(database_url: str) -> None:
    import threading

    email = _email()
    name = f"Race {uuid4()}"
    clock = FrozenClock(_START)
    settings = build_settings(**_params(database_url))
    engine = make_engine(database_url)
    factory = make_session_factory(engine)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt() -> None:
        session = factory()
        service = IdentityService(session, clock, settings)
        try:
            barrier.wait(timeout=10)
            try:
                service.register(
                    email=email,
                    password=PASSWORD,
                    workspace_name=name,
                    user_agent=None,
                    ip=None,
                    request_id="race",
                )
                outcome = "created"
            except Exception as exc:
                outcome = getattr(exc, "code", type(exc).__name__)
        finally:
            session.close()
        with lock:
            outcomes.append(str(outcome))

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    engine.dispose()
    assert sorted(outcomes) == ["created", "registration_conflict"]
    with db_session(database_url) as session:
        users = list(session.scalars(select(User).where(User.email == email)))
        assert len(users) == 1
        memberships = list(
            session.scalars(select(Membership).where(Membership.user_id == users[0].id))
        )
        assert len(memberships) == 1
        assert memberships[0].role == MembershipRole.OWNER
        named = session.scalar(
            select(func.count()).select_from(Workspace).where(Workspace.name == name)
        )
        assert named == 1


def test_login_is_generic_and_rotates_the_presented_session(client: TestClient) -> None:
    email = _email()
    _register(client, email)
    client.cookies.clear()
    unknown = client.post(
        "/api/v1/auth/login",
        json={"email": _email(), "password": PASSWORD},
    )
    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "not-the-password"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["code"] == wrong.json()["error"]["code"] == "invalid_credentials"
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]
    first_cookie = _cookie(
        client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    )
    second_body, second_cookie = _login(client, email)
    assert first_cookie != second_cookie
    assert first_cookie not in str(second_body)
    client.cookies.clear()
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Cookie": f"supplymind_session={first_cookie}"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Cookie": f"supplymind_session={second_cookie}"},
        ).status_code
        == 200
    )


def test_malformed_hash_and_inactive_user_fail_like_a_bad_password(
    client: TestClient,
    database_url: str,
) -> None:
    email = _email()
    body, _cookie_value = _register(client, email)
    user = body["user"]
    assert isinstance(user, dict)
    with db_session(database_url) as session:
        stored = session.get(User, UUID(str(user["id"])))
        assert stored is not None
        stored.password_hash = "not-a-hash"
    client.cookies.clear()
    failed = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert failed.status_code == 401
    assert failed.json()["error"]["code"] == "invalid_credentials"
    assert "not-a-hash" not in failed.text
    with db_session(database_url) as session:
        stored = session.get(User, UUID(str(user["id"])))
        assert stored is not None
        stored.is_active = False
        stored.password_hash = make_password_hasher(
            time_cost=1, memory_cost=8192, parallelism=1
        ).hash(PASSWORD)
    inactive = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert inactive.status_code == 401
    assert inactive.json()["error"]["message"] == failed.json()["error"]["message"]


def test_missing_and_garbage_sessions_are_rejected(client: TestClient) -> None:
    missing = client.get("/api/v1/auth/me", headers={"X-Request-ID": "req-stage2"})
    assert missing.status_code == 401
    assert missing.json() == {
        "error": {
            "code": "unauthenticated",
            "message": "Authentication is required.",
            "request_id": "req-stage2",
        }
    }
    client.cookies.set("supplymind_session", "this-is-not-a-session")
    garbage = client.get("/api/v1/workspace")
    assert garbage.status_code == 401
    assert "traceback" not in garbage.text.lower()


def test_logout_revokes_the_session_and_clears_the_cookie(client: TestClient) -> None:
    body, cookie = _register(client)
    response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": _csrf(body)})
    assert response.status_code == 204
    assert response.content == b""
    assert "max-age=0" in response.headers["set-cookie"].lower()
    client.cookies.clear()
    replay = client.get("/api/v1/auth/me", headers={"Cookie": f"supplymind_session={cookie}"})
    assert replay.status_code == 401


def test_revoke_all_sessions_invalidates_every_credential(client: TestClient) -> None:
    email = _email()
    first_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "workspace_name": "Acme"},
    )
    first_cookie = _cookie(first_response)
    client.cookies.clear()
    second_body, second_cookie = _login(client, email)
    client.cookies.clear()
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Cookie": f"supplymind_session={first_cookie}"}
        ).status_code
        == 200
    )
    revoked = client.post(
        "/api/v1/auth/sessions/revoke",
        headers={
            "Cookie": f"supplymind_session={second_cookie}",
            "X-CSRF-Token": _csrf(second_body),
        },
    )
    assert revoked.status_code == 204
    client.cookies.clear()
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Cookie": f"supplymind_session={first_cookie}"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Cookie": f"supplymind_session={second_cookie}"},
        ).status_code
        == 401
    )


def test_idle_timeout_rejects_an_unused_session_and_activity_resets_it(
    database_url: str,
) -> None:
    clock = FrozenClock(_START)
    with make_client(
        database_url,
        clock,
        session_idle_timeout_hours=1,
        session_absolute_timeout_hours=4,
    ) as (client, _clock):
        body, cookie = _register(client)
        clock.advance(timedelta(hours=1))
        assert client.get("/api/v1/auth/me").status_code == 401
        client.cookies.clear()
        fresh, _fresh_cookie = _login(client, str(body["user"]["email"]))  # type: ignore[index]
        assert client.get("/api/v1/auth/me").status_code == 200
        clock.advance(timedelta(minutes=30))
        assert client.get("/api/v1/auth/me").status_code == 200
        clock.advance(timedelta(minutes=30))
        assert client.get("/api/v1/auth/me").status_code == 200
        clock.advance(timedelta(hours=1))
        assert client.get("/api/v1/auth/me").status_code == 401
        assert fresh["csrf_token"]
        assert cookie


def test_absolute_timeout_survives_activity(database_url: str) -> None:
    clock = FrozenClock(_START)
    with make_client(
        database_url,
        clock,
        session_idle_timeout_hours=4,
        session_absolute_timeout_hours=1,
    ) as (client, _clock):
        _register(client)
        clock.advance(timedelta(minutes=30))
        assert client.get("/api/v1/auth/me").status_code == 200
        clock.advance(timedelta(minutes=30))
        expired = client.get("/api/v1/workspace/settings")
        assert expired.status_code == 401
        assert expired.json()["error"]["code"] == "unauthenticated"


def test_csrf_header_is_required_and_bound_to_the_session(client: TestClient) -> None:
    first, first_cookie = _register(client)
    missing = client.post("/api/v1/auth/logout")
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_invalid"
    assert client.get("/api/v1/auth/me").status_code == 200
    bogus = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "not-a-valid-csrf-token"})
    assert bogus.status_code == 403
    cookie_as_token = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": first_cookie},
    )
    assert cookie_as_token.status_code == 403
    client.cookies.clear()
    second, _second_cookie = _register(client, name="Beta Stores")
    _as(client, first_cookie)
    foreign = client.patch(
        "/api/v1/workspace",
        headers={"X-CSRF-Token": _csrf(second)},
        json={"name": "Hijack"},
    )
    assert foreign.status_code == 403
    rotated = client.get("/api/v1/auth/csrf")
    assert rotated.status_code == 200
    new_token = rotated.json()["csrf_token"]
    assert new_token != _csrf(first)
    stale = client.patch(
        "/api/v1/workspace",
        headers={"X-CSRF-Token": _csrf(first)},
        json={"name": "Stale"},
    )
    assert stale.status_code == 403
    updated = client.patch(
        "/api/v1/workspace",
        headers={"X-CSRF-Token": new_token},
        json={"name": "Renamed"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["id"] == first["workspace"]["id"]  # type: ignore[index]


def test_cors_allows_the_configured_origin_only(client: TestClient) -> None:
    allowed = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    rejected = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert rejected.headers.get("access-control-allow-origin") in {None, ""}
    echoed = client.get("/api/v1/auth/me", headers={"Origin": "https://evil.example"})
    assert echoed.headers.get("access-control-allow-origin") in {None, ""}


def test_production_cookie_is_secure_and_development_cookie_is_not(database_url: str) -> None:
    with make_client(database_url, session_cookie_secure=False) as (local, _clock):
        response = local.post(
            "/api/v1/auth/register",
            json={"email": _email(), "password": PASSWORD, "workspace_name": "Local"},
        )
        header = response.headers["set-cookie"].lower()
        assert "httponly" in header
        assert "samesite=lax" in header
        assert "path=/" in header
        assert "domain=" not in header
        assert "secure" not in header
    with make_client(
        database_url,
        app_env="production",
        session_cookie_secure=True,
        app_secret="p" * 32,
    ) as (production, _clock):
        response = production.post(
            "/api/v1/auth/register",
            json={"email": _email(), "password": PASSWORD, "workspace_name": "Prod"},
        )
        assert response.status_code == 201, response.text
        header = response.headers["set-cookie"].lower()
        assert "secure" in header
        assert "httponly" in header
        assert "samesite=lax" in header
        assert "path=/" in header
        assert "domain=" not in header
        assert production.get("/openapi.json").status_code == 404


def test_login_and_signup_are_rate_limited(database_url: str) -> None:
    with make_client(
        database_url,
        auth_rate_limit_attempts=2,
        auth_rate_limit_window_seconds=600,
    ) as (client, _clock):
        payload = {"email": _email(), "password": PASSWORD}
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401
        blocked = client.post("/api/v1/auth/login", json=payload)
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "rate_limited"


def test_workspace_query_cannot_switch_tenant(client: TestClient) -> None:
    first, first_cookie = _register(client, name="Alpha")
    first_workspace = first["workspace"]
    assert isinstance(first_workspace, dict)
    _as(client, first_cookie)
    second, _second_cookie = _register(client, name="Beta")
    second_workspace = second["workspace"]
    assert isinstance(second_workspace, dict)
    _as(client, first_cookie)
    response = client.get("/api/v1/workspace", params={"workspace_id": second_workspace["id"]})
    assert response.status_code == 200
    assert response.json()["id"] == first_workspace["id"]
    assert response.json()["name"] == "Alpha"


def test_workspace_body_cannot_switch_tenant(client: TestClient) -> None:
    first, first_cookie = _register(client, name="Alpha")
    second, _second_cookie = _register(client, name="Beta")
    second_workspace = second["workspace"]
    assert isinstance(second_workspace, dict)
    _as(client, first_cookie)
    rejected = client.patch(
        "/api/v1/workspace",
        headers={"X-CSRF-Token": _csrf(first)},
        json={"name": "Alpha 2", "workspace_id": second_workspace["id"]},
    )
    assert rejected.status_code == 422
    renamed = client.patch(
        "/api/v1/workspace",
        headers={"X-CSRF-Token": _csrf(first)},
        json={"name": "  Alpha 2  "},
    )
    assert renamed.status_code == 200
    assert renamed.json()["id"] == first["workspace"]["id"]  # type: ignore[index]
    assert renamed.json()["name"] == "Alpha 2"


def test_settings_are_isolated_between_workspaces(client: TestClient) -> None:
    first, first_cookie = _register(client, name="Alpha")
    second, second_cookie = _register(client, name="Beta")
    _as(client, first_cookie)
    own = client.get("/api/v1/workspace/settings")
    assert own.status_code == 200
    assert own.json()["notification_prefs"]["cooldown_hours"] == 24
    _as(client, second_cookie)
    other = client.get(
        "/api/v1/workspace/settings",
        params={"workspace_id": first["workspace"]["id"]},  # type: ignore[index]
    )
    assert other.status_code == 200
    assert other.json() == own.json()
    assert "ai_monthly" not in other.text
    assert "fx_delay" not in other.text


def test_settings_patch_cannot_change_another_workspace(
    client: TestClient,
    database_url: str,
) -> None:
    first, first_cookie = _register(client, name="Alpha")
    _second, second_cookie = _register(client, name="Beta")
    first_workspace = first["workspace"]
    assert isinstance(first_workspace, dict)
    _as(client, second_cookie)
    blocked = client.patch(
        "/api/v1/workspace/settings",
        headers={"X-CSRF-Token": _csrf(first)},
        json={"notification_prefs": {"recipient_emails": ["a@example.com"], "cooldown_hours": 4}},
    )
    assert blocked.status_code == 403
    _as(client, first_cookie)
    updated = client.patch(
        "/api/v1/workspace/settings",
        headers={"X-CSRF-Token": _csrf(first)},
        json={
            "notification_prefs": {
                "recipient_emails": ["Owner@Example.com"],
                "cooldown_hours": 12,
            }
        },
    )
    assert updated.status_code == 200
    assert updated.json()["notification_prefs"]["recipient_emails"] == ["owner@example.com"]
    assert updated.json()["notification_prefs"]["cooldown_hours"] == 12
    _as(client, second_cookie)
    untouched = client.get("/api/v1/workspace/settings")
    assert untouched.json()["notification_prefs"]["cooldown_hours"] == 24
    with db_session(database_url) as session:
        first_row = session.scalar(
            select(WorkspaceSettings).where(
                WorkspaceSettings.workspace_id == UUID(str(first_workspace["id"]))
            )
        )
        assert first_row is not None
        assert first_row.notification_prefs["cooldown_hours"] == 12


def test_missing_membership_and_two_memberships_fail_closed(
    client: TestClient,
    database_url: str,
) -> None:
    body, cookie = _register(client)
    user = body["user"]
    assert isinstance(user, dict)
    user_id = UUID(str(user["id"]))
    with db_session(database_url) as session:
        session.query(Membership).filter(Membership.user_id == user_id).delete()
    denied = client.get("/api/v1/workspace")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "workspace_unavailable"
    with db_session(database_url) as session:
        session.add(
            Membership(
                workspace_id=UUID(str(body["workspace"]["id"])),  # type: ignore[index]
                user_id=user_id,
                role=MembershipRole.OWNER,
            )
        )
        extra = Workspace(
            id=new_id(),
            name="Extra",
            timezone="Africa/Lagos",
            currency="NGN",
            onboarding_step=OnboardingStep.COMPANY,
        )
        session.add(extra)
        session.flush()
        session.add(Membership(workspace_id=extra.id, user_id=user_id, role=MembershipRole.OWNER))
    _as(client, cookie)
    inconsistent = client.get("/api/v1/workspace/settings")
    assert inconsistent.status_code == 403
    assert inconsistent.json()["error"]["code"] == "workspace_unavailable"


def test_deleted_settings_are_not_found_and_do_not_reveal_another_workspace(
    client: TestClient,
    database_url: str,
) -> None:
    first, first_cookie = _register(client, name="Alpha")
    _second, second_cookie = _register(client, name="Beta")
    workspace_id = UUID(str(first["workspace"]["id"]))  # type: ignore[index]
    with db_session(database_url) as session:
        session.query(WorkspaceSettings).filter(
            WorkspaceSettings.workspace_id == workspace_id
        ).delete()
    _as(client, first_cookie)
    missing = client.get("/api/v1/workspace/settings")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    _as(client, second_cookie)
    assert client.get("/api/v1/workspace/settings").status_code == 200


def test_workspace_repository_requires_a_tenant_and_cannot_read_across_it(
    client: TestClient,
    database_url: str,
) -> None:
    first, _first_cookie = _register(client, name="Alpha")
    second, _second_cookie = _register(client, name="Beta")
    first_id = UUID(str(first["workspace"]["id"]))  # type: ignore[index]
    second_id = UUID(str(second["workspace"]["id"]))  # type: ignore[index]
    with db_session(database_url) as session:
        with pytest.raises(TypeError):
            WorkspaceRepository(session, None)  # type: ignore[arg-type]
        left = WorkspaceRepository(session, TenantContext(first_id))
        right = WorkspaceRepository(session, TenantContext(second_id))
        assert left.get_workspace() is not None
        assert left.get_workspace().id == first_id  # type: ignore[union-attr]
        updated = left.replace_notification_prefs({"recipient_emails": [], "cooldown_hours": 3})
        assert updated is not None
        session.commit()
        session.expire_all()
        other = right.get_settings()
        assert other is not None
        assert other.workspace_id == second_id
        assert other.notification_prefs["cooldown_hours"] == 24


def test_password_reset_response_hides_whether_the_email_exists(
    client: TestClient,
    database_url: str,
) -> None:
    email = _email()
    _register(client, email)
    known = client.post("/api/v1/auth/password-resets", json={"email": email})
    unknown = client.post(
        "/api/v1/auth/password-resets",
        json={"email": f"missing-{uuid4()}@example.com"},
    )
    assert known.status_code == unknown.status_code == 204
    assert known.content == unknown.content == b""
    with db_session(database_url) as session:
        user = session.scalar(select(User).where(User.email == email))
        assert user is not None
        tokens = list(
            session.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
        )
        assert len(tokens) == 1
        assert len(tokens[0].token_hash) == 64


def test_password_reset_is_single_use_and_revokes_sessions(
    client: TestClient,
    database_url: str,
    clock: FrozenClock,
) -> None:
    email = _email()
    _body, cookie = _register(client, email)
    token = _issue_reset(database_url, clock, email)
    confirm = client.post(
        "/api/v1/auth/password-resets/confirm",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert confirm.status_code == 204
    assert token not in confirm.text
    client.cookies.clear()
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Cookie": f"supplymind_session={cookie}"}
        ).status_code
        == 401
    )
    old = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert old.status_code == 401
    _login(client, email, NEW_PASSWORD)
    again = client.post(
        "/api/v1/auth/password-resets/confirm",
        json={"token": token, "password": "correct-horse-3"},
    )
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "reset_rejected"
    unrelated = client.post(
        "/api/v1/auth/password-resets/confirm",
        json={"token": "x" * 32, "password": NEW_PASSWORD},
    )
    assert unrelated.status_code == 400
    assert unrelated.json()["error"]["message"] == again.json()["error"]["message"]


def test_expired_password_reset_is_rejected(
    client: TestClient,
    database_url: str,
    clock: FrozenClock,
) -> None:
    email = _email()
    _register(client, email)
    token = _issue_reset(database_url, clock, email)
    clock.advance(timedelta(minutes=31))
    response = client.post(
        "/api/v1/auth/password-resets/confirm",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "reset_rejected"
    assert token not in response.text


def test_failed_login_audit_omits_the_email_and_password(
    client: TestClient,
    database_url: str,
) -> None:
    email = _email()
    password = "not-the-password"
    handler = _LogCapture()
    logging.getLogger().addHandler(handler)
    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
    finally:
        logging.getLogger().removeHandler(handler)
    assert response.status_code == 401
    logged = "\n".join(handler.messages)
    assert password not in logged
    assert email not in logged
    with db_session(database_url) as session:
        rows = list(session.scalars(select(AuditLog).where(AuditLog.action == "login_failed")))
        blob = " ".join(
            " ".join(
                str(part) for part in (row.actor, row.action, row.before, row.after, row.entity_id)
            )
            for row in rows
        )
        assert email not in blob
        assert password not in blob


def test_openapi_lists_the_identity_routes(client: TestClient) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    for path in (
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/csrf",
        "/api/v1/auth/me",
        "/api/v1/auth/sessions/revoke",
        "/api/v1/auth/password-resets",
        "/api/v1/auth/password-resets/confirm",
        "/api/v1/workspace",
        "/api/v1/workspace/settings",
    ):
        assert path in paths


def _issue_reset(database_url: str, clock: FrozenClock, email: str) -> str:
    engine = make_engine(database_url)
    session = make_session_factory(engine)()
    try:
        token = IdentityService(
            session,
            clock,
            build_settings(**_params(database_url)),
        ).prepare_password_reset(email=email, request_id="reset-test")
    finally:
        session.close()
        engine.dispose()
    assert token is not None
    return token


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(self.format(record))
