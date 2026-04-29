"""
pytest configuration and shared fixtures.

LEARNING — conftest.py:
  This file is automatically loaded by pytest before any tests run.
  Fixtures defined here are available to ALL test files without importing.

LEARNING — pytest markers:
  We define custom markers so you can run subsets of tests:
    pytest tests/ -m "not e2e"   <- skip e2e tests (no Ollama needed)
    pytest tests/ -m "e2e"       <- only e2e tests
    pytest tests/ -v             <- all tests, verbose
"""

import pytest
from mocks.containers import MOCK_CONTAINERS


def pytest_configure(config):
    """Register custom markers to avoid warnings."""
    config.addinivalue_line(
        "markers",
        "e2e: marks tests as end-to-end (requires Ollama running locally)"
    )


@pytest.fixture
def mock_containers():
    """
    Fixture: provides the mock container data to any test that needs it.

    LEARNING — pytest fixtures:
      Fixtures are reusable setup functions. Use them instead of copy-pasting
      setup code in every test. The fixture name becomes a parameter in the test function.
    """
    return MOCK_CONTAINERS


@pytest.fixture
def expected_unhealthy():
    """Fixture: returns the names of containers we expect to be unhealthy."""
    return {
        name
        for name, data in MOCK_CONTAINERS.items()
        if data["status"] != "running"
    }


@pytest.fixture
def expected_healthy():
    """Fixture: returns the names of containers we expect to be running."""
    return {
        name
        for name, data in MOCK_CONTAINERS.items()
        if data["status"] == "running"
    }
