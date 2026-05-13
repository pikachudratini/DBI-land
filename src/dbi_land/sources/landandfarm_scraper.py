"""Land and Farm (landandfarm.com, CoStar) scraper.

URL structure:
    /search/<state-slug>-land-for-sale/                    (all sizes)
    /search/<state-slug>-land-for-sale/acres-over-<min>/   (acreage filter)
    /search/<state-slug>-land-for-sale/acres-over-<min>/page-<N>/

Listing tiles anchor on `<a href="/property/<slug>-<id>/">`. We walk up to
the smallest containing element with `$` and `acres` in its text and parse
with regex (largest-$ wins to skip per-parcel breakdown amounts in the
description text).

Note: Land and Farm shares heavy listing syndication with LandWatch. Cross-
source deduplication isn't done by the JSONL store (which keys on
source:listing_id); we keep both because the IDs differ and unique-only
listings do exist in each source.
"""
from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator

from bs4 import BeautifulSoup

from dbi_land.models import Listing

LANDANDFARM_HOST = "https://www.landandfarm.com"

_STATE_SLUG = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new-hampshire", "NJ": "new-jersey", "NM": "new-mexico", "NY": "new-york",
    "NC": "north-carolina", "ND": "north-dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode-island", "SC": "south-carolina",
    "SD": "south-dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west-virginia",
    "WI": "wisconsin", "WY": "wyoming",
}

_PROP_RE = re.compile(r"^/property/[a-z0-9-]+-(\d+)/?$", re.I)
_PRICE_RE = re.compile(r"\$([\d,]+)")
_ACRES_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:±\s*)?acres?", re.I)
_COUNTY_RE = re.compile(r",\s*([A-Z][A-Za-z .'-]+?)\s+County")
_CITYSTATE_RE = re.compile(r"([A-Z][A-Za-z .'-]+),\s*([A-Z]{2})(?:,?\s*\d{5})?")


def state_url(state_code: str, min_acres: int = 200, page: int = 1) -> str:
    slug = _STATE_SLUG[state_code.upper()]
    base = f"{LANDANDFARM_HOST}/search/{slug}-land-for-sale/acres-over-{min_acres}"
    base = base + "/"
    return base if page == 1 else f"{base}page-{page}/"


def _parse_float(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _find_tile_container(anchor):
    el = anchor
    for _ in range(8):
        if el.parent is None:
            return None
        el = el.parent
        text = el.get_text(" | ", strip=True)
        if "$" in text and "cre" in text.lower() and len(text) > 80:
            return el
    return None


def _parse_tile(anchor, state_code: str) -> Listing | None:
    m = _PROP_RE.search(anchor["href"])
    if not m:
        return None
    pid = m.group(1)
    container = _find_tile_container(anchor)
    if container is None:
        return None
    text = container.get_text(" | ", strip=True)

    prices = [_parse_float(p.group(1)) for p in _PRICE_RE.finditer(text)]
    prices = [p for p in prices if p is not None and p >= 1000]
    price = max(prices) if prices else None
    acres_match = _ACRES_RE.search(text)
    if price is None or not acres_match:
        return None
    acres = _parse_float(acres_match.group(1))
    if acres is None or acres <= 0 or price <= 0:
        return None

    county = None
    cm = _COUNTY_RE.search(text)
    if cm:
        county = cm.group(1).strip()

    title = ""
    cs = _CITYSTATE_RE.search(text)
    if cs:
        title = cs.group(0)

    return Listing(
        listing_id=pid,
        source="landandfarm",
        url=f"{LANDANDFARM_HOST}{anchor['href']}",
        state=state_code.upper(),
        county=county,
        acres=acres,
        price_usd=price,
        lat=None,
        lon=None,
        title=title,
    )


def parse_state_html(html: str, state_code: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Listing] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        if not _PROP_RE.search(a["href"]):
            continue
        listing = _parse_tile(a, state_code)
        if listing is None or listing.listing_id in seen:
            continue
        seen.add(listing.listing_id)
        out.append(listing)
    return out


def total_pages(html: str) -> int:
    """LAF doesn't expose page anchors in HTML; rely on driver counting.

    Returns 1 unconditionally; the driver walks pages until a page returns no
    new listings.
    """
    return 1


@dataclass
class LandAndFarmScraperConfig:
    min_acres: int = 200
    max_pages_per_state: int = 5
    page_delay_range: tuple[float, float] = (2.0, 4.0)
    state_delay_range: tuple[float, float] = (4.0, 8.0)
    nav_timeout_ms: int = 30000
    challenge_wait_s: float = 12.0
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )
    viewport: dict = field(default_factory=lambda: {"width": 1366, "height": 900})


class LandAndFarmScraper:
    name = "landandfarm"

    def __init__(
        self,
        states: Iterable[str],
        *,
        config: LandAndFarmScraperConfig | None = None,
        page_fetcher=None,
    ):
        self.states = [s.upper() for s in states]
        self.config = config or LandAndFarmScraperConfig()
        self._page_fetcher = page_fetcher

    def fetch(self) -> Iterator[Listing]:
        fetch_page = self._page_fetcher or self._playwright_fetcher()
        try:
            for i, state in enumerate(self.states):
                if state not in _STATE_SLUG:
                    continue
                yield from self._fetch_state(state, fetch_page)
                if i < len(self.states) - 1:
                    reset = getattr(fetch_page, "reset", None)
                    if callable(reset):
                        reset()
                    time.sleep(random.uniform(*self.config.state_delay_range))
        finally:
            close = getattr(fetch_page, "close", None)
            if callable(close):
                close()

    def _fetch_state(self, state: str, fetch_page) -> Iterator[Listing]:
        seen: set[str] = set()
        for page in range(1, self.config.max_pages_per_state + 1):
            if page > 1:
                time.sleep(random.uniform(*self.config.page_delay_range))
            html = fetch_page(state_url(state, self.config.min_acres, page))
            if not html:
                break
            new_count = 0
            for listing in parse_state_html(html, state):
                if listing.listing_id in seen:
                    continue
                seen.add(listing.listing_id)
                new_count += 1
                yield listing
            if new_count == 0:
                break

    def _playwright_fetcher(self):
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth

        cfg = self.config
        pw = sync_playwright().start()
        state = {"browser": None, "ctx": None, "page": None}

        def open_session() -> None:
            browser = pw.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            ctx = browser.new_context(
                user_agent=cfg.user_agent,
                viewport=cfg.viewport,
                locale="en-US",
            )
            Stealth().apply_stealth_sync(ctx)
            page = ctx.new_page()
            state["browser"], state["ctx"], state["page"] = browser, ctx, page

        def close_session() -> None:
            browser = state.get("browser")
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            state["browser"] = state["ctx"] = state["page"] = None

        open_session()

        def fetch(url: str) -> str | None:
            page = state["page"]
            try:
                page.goto(url, timeout=cfg.nav_timeout_ms, wait_until="domcontentloaded")
            except Exception:
                return None
            deadline = time.monotonic() + cfg.challenge_wait_s
            while time.monotonic() < deadline:
                title = page.title()
                if "Just a moment" not in title and "Verification" not in title:
                    break
                time.sleep(1.0)
            page.evaluate("window.scrollBy(0, 4000)")
            time.sleep(0.8)
            return page.content()

        def reset() -> None:
            close_session()
            open_session()

        def close() -> None:
            close_session()
            pw.stop()

        fetch.close = close  # type: ignore[attr-defined]
        fetch.reset = reset  # type: ignore[attr-defined]
        return fetch
