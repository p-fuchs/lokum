from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def olx_offer_html() -> str:
    return (FIXTURES_DIR / "olx_offer.html").read_text()


@pytest.fixture
def olx_search_html() -> str:
    return (FIXTURES_DIR / "olx_search.html").read_text()
