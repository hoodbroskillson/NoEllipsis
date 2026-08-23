from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

from noellipsis.config import Config

settings.register_profile(
    "ci",
    max_examples=40,
    deadline=None,
    suppress_health_check=(HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.function_scoped_fixture),
)
settings.load_profile("ci")


@pytest.fixture
def cfg() -> Config:
    return Config()


@pytest.fixture
def examples() -> Path:
    return Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def fixtures() -> Path:
    return Path(__file__).resolve().parent / "fixtures"
