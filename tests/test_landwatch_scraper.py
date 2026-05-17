from __future__ import annotations

from pathlib import Path

import pytest

from dbi_land.sources.landwatch_scraper import (
    LandWatchScraper,
    LandWatchScraperConfig,
    parse_state_html,
    state_url,
    total_pages,
)

FIXTURE = Path(__file__).parent / "fixtures" / "landwatch_iowa_200plus.html"


@pytest.fixture(scope="module")
def iowa_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_state_url_uses_slug_and_acreage_filter():
    assert state_url("IA", 200, 1) == "https://www.landwatch.com/iowa-land-for-sale/acres-over-200"
    assert state_url("IA", 200, 3) == "https://www.landwatch.com/iowa-land-for-sale/acres-over-200/page-3"
    assert state_url("NJ", 200, 2) == "https://www.landwatch.com/new-jersey-land-for-sale/acres-over-200/page-2"


def test_parse_state_html_extracts_listings(iowa_html):
    listings = parse_state_html(iowa_html, "IA")
    assert len(listings) >= 20
    for l in listings:
        assert l.source == "landwatch"
        assert l.state == "IA"
        assert l.url.startswith("https://www.landwatch.com/")
        assert l.acres >= 200, "URL filter is set to >=200 ac; all parsed tiles should clear it"
        assert l.price_usd > 0
        assert l.listing_id.isdigit()


def test_parse_extracts_county_from_url(iowa_html):
    listings = parse_state_html(iowa_html, "IA")
    counties = {l.county for l in listings if l.county}
    assert len(counties) >= 3, "should detect multiple counties"
    for c in counties:
        assert c.istitle() or " " in c  # title-cased name from URL slug


def test_parse_picks_largest_price_in_tile(iowa_html):
    # parser should pick the actual list price over any "$50k drop" decoration
    listings = parse_state_html(iowa_html, "IA")
    assert all(l.price_usd >= 50_000 for l in listings), \
        "parser must skip small price callouts like '$50k drop'"


def test_total_pages_reads_pagination(iowa_html):
    assert total_pages(iowa_html) >= 2


def test_scraper_with_injected_fetcher(iowa_html):
    calls: list[str] = []

    def fake_fetch(url: str) -> str:
        calls.append(url)
        return iowa_html

    cfg = LandWatchScraperConfig(
        min_acres=200, max_pages_per_state=3,
        page_delay_range=(0.0, 0.0), state_delay_range=(0.0, 0.0),
    )
    scraper = LandWatchScraper(["IA"], config=cfg, page_fetcher=fake_fetch)
    listings = list(scraper.fetch())

    # Same page returned twice -> dedup bails after page 2
    assert calls[0] == state_url("IA", 200, 1)
    assert calls[1] == state_url("IA", 200, 2)
    ids = {l.listing_id for l in listings}
    assert len(ids) == len(listings)


def test_scraper_skips_unknown_state():
    cfg = LandWatchScraperConfig(
        page_delay_range=(0.0, 0.0), state_delay_range=(0.0, 0.0),
    )
    scraper = LandWatchScraper(["ZZ"], config=cfg, page_fetcher=lambda u: "")
    assert list(scraper.fetch()) == []
