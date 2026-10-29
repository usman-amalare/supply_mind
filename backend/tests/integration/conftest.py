"""PostgreSQL for schema tests. Uses TEST_DATABASE_URL when set, otherwise Testcontainers."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from tests.integration.database import migrate, normalize_database_url


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    external = os.environ.get("TEST_DATABASE_URL")
    if external:
        url = normalize_database_url(external)
        migrate(url, "head")
        yield url
        return

    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:16") as postgres:
        url = normalize_database_url(postgres.get_connection_url())
        migrate(url, "head")
        yield url
