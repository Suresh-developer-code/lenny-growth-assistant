"""Shared pytest fixtures.

Tests are designed to run WITHOUT a live Postgres/Ollama/Anthropic dependency
by default (they mock the network/DB boundary), so `pytest` works out of the
box for an evaluator who hasn't stood up docker-compose yet. A smaller set of
integration tests (marked `@pytest.mark.integration`) does hit a real DB and
is skipped unless RUN_INTEGRATION_TESTS=1 is set — see README's test section.
"""
import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires live Postgres/Ollama")


@pytest.fixture
def anyio_backend():
    return "asyncio"


SKIP_INTEGRATION = os.environ.get("RUN_INTEGRATION_TESTS") != "1"
