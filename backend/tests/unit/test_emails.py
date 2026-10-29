from __future__ import annotations

import pytest

from supplymind.modules.identity.emails import normalize_email


def test_email_is_stripped_and_casefolded() -> None:
    assert normalize_email("  User+Tag@Example.COM ") == "user+tag@example.com"


def test_email_rejects_malformed_values_without_echoing_them() -> None:
    for value in ("not-an-email", "a@b", "user@localhost", "a b@example.com", "@example.com"):
        with pytest.raises(ValueError, match="invalid email") as caught:
            normalize_email(value)
        assert value not in str(caught.value)
