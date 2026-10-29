from __future__ import annotations

import pytest

from supplymind.core.security import (
    dummy_password_check,
    hash_ip,
    hash_password,
    hash_token,
    new_token,
    password_is_acceptable,
    token_matches,
    verify_password,
)


def test_password_policy_bounds() -> None:
    assert password_is_acceptable("1234567890")
    assert not password_is_acceptable("too-short")
    assert not password_is_acceptable("x" * 129)


def test_password_hash_round_trip() -> None:
    stored = hash_password("a-real-password")
    assert stored != "a-real-password"
    assert stored.startswith("$argon2id$")
    assert verify_password("a-real-password", stored)
    assert not verify_password("another-password", stored)
    assert not verify_password("a-real-password", "not-a-hash")


def test_dummy_password_check_does_not_raise() -> None:
    dummy_password_check("whatever-the-user-typed")


def test_token_hash_matches_only_the_original() -> None:
    token = new_token()
    stored = hash_token(token)
    assert len(stored) == 64
    assert token_matches(token, stored)
    assert not token_matches(new_token(), stored)
    assert not token_matches(token, "short")


def test_ip_hash_uses_the_secret_and_hides_the_address() -> None:
    first = hash_ip("203.0.113.8", "s" * 32)
    second = hash_ip("203.0.113.8", "t" * 32)
    assert first != second
    assert "203.0.113.8" not in first
    with pytest.raises(ValueError):
        hash_ip("203.0.113.8", "")
