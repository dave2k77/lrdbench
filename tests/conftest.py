from pathlib import Path

import pytest
from pytest import Config


def pytest_configure(config: Config) -> None:
    config.addinivalue_line("markers", "integration: end-to-end integration tests")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Repository root (directory containing pyproject.toml)."""
    return Path(__file__).resolve().parents[1]
