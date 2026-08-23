from __future__ import annotations

from pathlib import Path

import pytest

from noellipsis.config import Config


@pytest.fixture
def cfg() -> Config:
    return Config()


@pytest.fixture
def examples() -> Path:
    return Path(__file__).resolve().parents[1] / "examples"
