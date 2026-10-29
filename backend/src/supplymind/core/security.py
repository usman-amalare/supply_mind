"""Password hashing, token hashing, CSRF comparison, and IP hashing."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_MIN_PASSWORD_LENGTH = 10
_MAX_PASSWORD_LENGTH = 128
# RFC 9106 second recommended option. PasswordHasher() uses this profile.
_DEFAULT_TIME_COST = 3
_DEFAULT_MEMORY_COST = 65536
_DEFAULT_PARALLELISM = 4
_hasher = PasswordHasher(
    time_cost=_DEFAULT_TIME_COST,
    memory_cost=_DEFAULT_MEMORY_COST,
    parallelism=_DEFAULT_PARALLELISM,
    type=Type.ID,
)
# Not an account password. Hashed once so unknown-user logins can spend the same work.
_DUMMY_PASSWORD_HASH = _hasher.hash("x" * _MAX_PASSWORD_LENGTH)
_dummy_lock = threading.Lock()
_dummy_hashes: dict[tuple[int, int, int], str] = {
    (_DEFAULT_TIME_COST, _DEFAULT_MEMORY_COST, _DEFAULT_PARALLELISM): _DUMMY_PASSWORD_HASH
}


def password_is_acceptable(password: str) -> bool:
    return _MIN_PASSWORD_LENGTH <= len(password) <= _MAX_PASSWORD_LENGTH


def make_password_hasher(*, time_cost: int, memory_cost: int, parallelism: int) -> PasswordHasher:
    """Build an Argon2id hasher. Parameters come from settings, not from the request."""
    return PasswordHasher(
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        type=Type.ID,
    )


def hash_password(password: str, hasher: PasswordHasher | None = None) -> str:
    if not password_is_acceptable(password):
        raise ValueError("password does not meet policy")
    return (hasher or _hasher).hash(password)


def verify_password(
    password: str,
    password_hash: str,
    hasher: PasswordHasher | None = None,
) -> bool:
    try:
        return (hasher or _hasher).verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_password_check(
    password: str,
    hasher: PasswordHasher | None = None,
    *,
    time_cost: int = _DEFAULT_TIME_COST,
    memory_cost: int = _DEFAULT_MEMORY_COST,
    parallelism: int = _DEFAULT_PARALLELISM,
) -> None:
    """Spend a password verification without revealing the result."""
    active = hasher or _hasher
    key = (time_cost, memory_cost, parallelism)
    with _dummy_lock:
        stored = _dummy_hashes.get(key)
        if stored is None:
            stored = active.hash("x" * _MAX_PASSWORD_LENGTH)
            _dummy_hashes[key] = stored
    verify_password(password, stored, active)


def password_needs_rehash(password_hash: str, hasher: PasswordHasher | None = None) -> bool:
    try:
        return (hasher or _hasher).check_needs_rehash(password_hash)
    except (InvalidHashError, VerificationError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str, expected_hash: str) -> bool:
    actual = hash_token(token)
    if len(actual) != len(expected_hash):
        return False
    return hmac.compare_digest(actual, expected_hash)


def hash_ip(ip: str, secret: str) -> str:
    if not secret:
        raise ValueError("IP hashing requires the application secret")
    return hmac.new(secret.encode("utf-8"), ip.encode("utf-8"), hashlib.sha256).hexdigest()
