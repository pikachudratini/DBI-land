from __future__ import annotations

from pathlib import Path

import pytest

from dbi_land.config import Criteria

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TEST_CRITERIA = FIXTURES / "test_criteria.yaml"


@pytest.fixture
def criteria() -> Criteria:
    return Criteria.from_yaml(TEST_CRITERIA)


@pytest.fixture
def sample_csv_path() -> Path:
    return EXAMPLES / "sample_listings.csv"
