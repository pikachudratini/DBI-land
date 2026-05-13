from __future__ import annotations

from pathlib import Path

import pytest

from dbi_land.sources.landsearch_scraper import (
    LandSearchScraper,
    LandSearchScraperConfig,
    parse_state_html,
    state_url,
    total_pages,
)

FIXTURE = Path(__file__).parent / "fixtures" / "landsearch_iowa.html"


@pytest.fixture(scope="module")
def iowa_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_state_url_uses_slug_and_pagination():
    assert state_url("IA", 1) == "https://www.landsearch.com/properties/state/iowa"
    assert state_url("IA", 3) == "https://www.landsearch.com/properties/state/iowa/p3"
    assert state_url("NJ", 2) == "https://www.landsearch.com/properties/state/new-jersey/p2"


def test_parse_state_html_extracts_listings(iowa_html):
    listings = parse_state_html(iowa_html, "IA")
    assert len(listings) >= 20, "expected many tiles per state page"
    for l in listings:
        assert l.source == "landsearch"
        assert l.state == "IA"
        assert l.url.startswith("https://www.landsearch.com/properties/")
        assert l.acres > 0
        assert l.price_usd > 0
        assert l.listing_id.isdigit()


def test_parse_skips_auction_min_price(iowa_html):
    listings = parse_state_html(iowa_html, "IA")
    auction_ids = {"5236650"}  # Jasper County auction tile with "$— min"
    found_ids = {l.listing_id for l in listings}
    assert not (auction_ids & found_ids), "auction tiles with no firm price should be skipped"


def test_parse_captures_county(iowa_html):
    listings = parse_state_html(iowa_html, "IA")
    by_id = {l.listing_id: l for l in listings}
    # "$2,197,000338 acres | Wayne County | Allerton, IA 50008"
    target = by_id.get("5251449")
    assert target is not None
    assert target.county == "Wayne"
    assert target.acres == 338.0
    assert target.price_usd == 2197000.0
    assert target.title == "Allerton, IA 50008"


def test_total_pages_reads_pagination(iowa_html):
    assert total_pages(iowa_html) >= 2


def test_scraper_with_injected_fetcher_paginates_and_dedupes(iowa_html):
    calls: list[str] = []

    def fake_fetch(url: str) -> str:
        calls.append(url)
        return iowa_html  # same page each time — should dedupe across pages

    cfg = LandSearchScraperConfig(
        max_pages_per_state=3,
        page_delay_range=(0.0, 0.0),
        state_delay_range=(0.0, 0.0),
    )
    scraper = LandSearchScraper(["IA"], config=cfg, page_fetcher=fake_fetch)
    listings = list(scraper.fetch())

    # Same page fetched 2x -> all listings on page 2 are dupes, so loop bails early.
    assert calls[0] == state_url("IA", 1)
    assert calls[1] == state_url("IA", 2)
    assert len(calls) == 2

    ids = {l.listing_id for l in listings}
    assert len(ids) == len(listings)


def test_scraper_skips_unknown_state():
    def fake_fetch(url: str) -> str:
        return ""

    cfg = LandSearchScraperConfig(
        page_delay_range=(0.0, 0.0), state_delay_range=(0.0, 0.0),
    )
    scraper = LandSearchScraper(["ZZ"], config=cfg, page_fetcher=fake_fetch)
    assert list(scraper.fetch()) == []
