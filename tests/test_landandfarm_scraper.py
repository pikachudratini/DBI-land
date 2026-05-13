from __future__ import annotations

from pathlib import Path

import pytest

from dbi_land.sources.landandfarm_scraper import (
    LandAndFarmScraper,
    LandAndFarmScraperConfig,
    parse_state_html,
    state_url,
)

FIXTURE = Path(__file__).parent / "fixtures" / "landandfarm_iowa_200plus.html"


@pytest.fixture(scope="module")
def iowa_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_state_url_uses_slug_and_acreage_filter():
    assert state_url("IA", 200, 1) == "https://www.landandfarm.com/search/iowa-land-for-sale/acres-over-200/"
    assert state_url("IA", 200, 3) == "https://www.landandfarm.com/search/iowa-land-for-sale/acres-over-200/page-3/"
    assert state_url("NJ", 200, 2) == "https://www.landandfarm.com/search/new-jersey-land-for-sale/acres-over-200/page-2/"


def test_parse_state_html_extracts_listings(iowa_html):
    listings = parse_state_html(iowa_html, "IA")
    assert len(listings) >= 10
    for l in listings:
        assert l.source == "landandfarm"
        assert l.state == "IA"
        assert l.url.startswith("https://www.landandfarm.com/property/")
        assert l.acres >= 200, "URL filter is >=200; parsed tiles should clear it"
        assert l.price_usd >= 1000
        assert l.listing_id.isdigit()


def test_parse_picks_largest_price(iowa_html):
    listings = parse_state_html(iowa_html, "IA")
    # multi-parcel listings carry many smaller $ amounts in the description;
    # parser must pick the top-line price, not a per-parcel breakdown.
    assert all(l.price_usd >= 100_000 for l in listings)


def test_parse_captures_county_and_citystate(iowa_html):
    listings = parse_state_html(iowa_html, "IA")
    with_county = [l for l in listings if l.county]
    assert len(with_county) >= 5
    with_title = [l for l in listings if l.title]
    assert len(with_title) >= 5
    for l in with_title:
        assert ", IA" in l.title


def test_scraper_with_injected_fetcher_paginates_and_dedupes(iowa_html):
    calls: list[str] = []

    def fake_fetch(url: str) -> str:
        calls.append(url)
        return iowa_html  # same page each time -> driver bails after dupes

    cfg = LandAndFarmScraperConfig(
        min_acres=200, max_pages_per_state=4,
        page_delay_range=(0.0, 0.0), state_delay_range=(0.0, 0.0),
    )
    scraper = LandAndFarmScraper(["IA"], config=cfg, page_fetcher=fake_fetch)
    listings = list(scraper.fetch())

    assert calls[0] == state_url("IA", 200, 1)
    assert calls[1] == state_url("IA", 200, 2)
    ids = {l.listing_id for l in listings}
    assert len(ids) == len(listings)
    assert len(calls) == 2  # page 2 was all dupes -> stop


def test_scraper_skips_unknown_state():
    cfg = LandAndFarmScraperConfig(
        page_delay_range=(0.0, 0.0), state_delay_range=(0.0, 0.0),
    )
    scraper = LandAndFarmScraper(["ZZ"], config=cfg, page_fetcher=lambda u: "")
    assert list(scraper.fetch()) == []
