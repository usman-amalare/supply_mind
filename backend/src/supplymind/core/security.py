"""Password hashing, token hashing, CSRF comparison, and IP hashing."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_MIN_PASSWORD_LENGTH = 10
_MAX_PASSWORD_LENGTH = 128
_hasher = PasswordHasher()
# Not an account password. Hashed once so unknown-user logins can spend the same work.
_DUMMY_PASSWORD_HASH = _hasher.hash("x" * _MAX_PASSWORD_LENGTH)


def password_is_acceptable(password: str) -> bool:
    return _MIN_PASSWORD_LENGTH <= len(password) <= _MAX_PASSWORD_LENGTH


def hash_password(password: str) -> str:
    if not password_is_acceptable(password):
        raise ValueError("password does not meet policy")
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_password_check(password: str) -> None:
    """Spend a password verification without revealing the result."""
    verify_password(password, _DUMMY_PASSWORD_HASH)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


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
