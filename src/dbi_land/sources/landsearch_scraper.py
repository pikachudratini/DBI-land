"""LandSearch scraper.

LandSearch search pages live at /properties/state/<state-name>/p<page>. The
markup is server-rendered, but the site is fronted by a Cloudflare JS
challenge, so we drive Chromium via Playwright (with stealth tweaks) to render
each page and then parse the resulting HTML with BeautifulSoup.

Listing tiles are <article class="preview $property"> elements. Their visible
text is a pipe-joined sequence like:

    Featured | 1 day ago | $2,197,000 | 338 acres | Wayne County | Allerton, IA 50008

Auction tiles show "$— min" for price; we skip those (no comparable price).

The parser (`parse_state_html`) is pure: it takes an HTML string and a state
code and returns Listing objects. The Playwright driver
(`LandSearchScraper`) is responsible for navigation, pagination, and rate
limiting.
"""
from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator

from bs4 import BeautifulSoup

from dbi_land.models import Listing

LANDSEARCH_HOST = "https://www.landsearch.com"

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

_TILE_HREF_RE = re.compile(r"^/properties/[^/]+/(\d+)$")
_PRICE_RE = re.compile(r"\$([\d,]+)")
_ACRES_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*acres?", re.I)
_COUNTY_RE = re.compile(r"([A-Za-z][A-Za-z .'-]*?)\s+County", re.I)
_CITYSTATE_RE = re.compile(r"^([A-Za-z][A-Za-z .'-]+),\s*([A-Z]{2})(?:\s+\d{5})?$")


def state_url(state_code: str, page: int = 1) -> str:
    slug = _STATE_SLUG[state_code.upper()]
    base = f"{LANDSEARCH_HOST}/properties/state/{slug}"
    return base if page == 1 else f"{base}/p{page}"


def _parse_float(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _parse_tile(art, state_code: str) -> Listing | None:
    href = None
    listing_id = None
    for a in art.find_all("a", href=True):
        m = _TILE_HREF_RE.match(a["href"])
        if m:
            href = a["href"]
            listing_id = m.group(1)
            break
    if not href or not listing_id:
        return None

    segments = [s.strip() for s in art.get_text(" | ", strip=True).split("|")]
    text = " | ".join(segments)

    # Tiles often carry callouts like "$20k drop" before the real price; take
    # the largest $-amount in the tile, which is always the list price.
    # Floor at $1000 to ignore stray "$1", "$50/mo financing", etc. — a real
    # parcel listing always asks at least four figures.
    price_values = [_parse_float(m.group(1)) for m in _PRICE_RE.finditer(text)]
    price_values = [p for p in price_values if p is not None and p >= 1000]
    price = max(price_values) if price_values else None
    acres_match = _ACRES_RE.search(text)
    if price is None or not acres_match:
        return None
    acres = _parse_float(acres_match.group(1))
    if acres is None or price <= 0 or acres <= 0:
        return None

    county = None
    cm = _COUNTY_RE.search(text)
    if cm:
        county = cm.group(1).strip()

    title = ""
    for seg in reversed(segments):
        m = _CITYSTATE_RE.match(seg)
        if m:
            title = seg
            break
    if not title:
        title = segments[-1][:120] if segments else ""

    return Listing(
        listing_id=listing_id,
        source="landsearch",
        url=f"{LANDSEARCH_HOST}{href}",
        state=state_code.upper(),
        county=county,
        acres=acres,
        price_usd=price,
        lat=None,
        lon=None,
        title=title,
    )


def parse_state_html(html: str, state_code: str) -> list[Listing]:
    """Extract listings from a rendered LandSearch state-page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[Listing] = []
    for art in soup.select("article.preview"):
        listing = _parse_tile(art, state_code)
        if listing is not None:
            out.append(listing)
    return out


def total_pages(html: str) -> int:
    """Read the highest page number from the pagination nav, or 1."""
    soup = BeautifulSoup(html, "html.parser")
    pages = [1]
    for a in soup.select('nav[aria-label*="pag" i] a, .pagination a'):
        href = a.get("href", "")
        m = re.search(r"/p(\d+)$", href)
        if m:
            pages.append(int(m.group(1)))
    return max(pages)


@dataclass
class LandSearchScraperConfig:
    max_pages_per_state: int = 3
    page_delay_range: tuple[float, float] = (2.0, 4.0)
    state_delay_range: tuple[float, float] = (4.0, 8.0)
    nav_timeout_ms: int = 30000
    challenge_wait_s: float = 16.0
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )
    viewport: dict = field(default_factory=lambda: {"width": 1366, "height": 900})


class LandSearchScraper:
    """Iterates states × pages, returns Listing objects.

    Filtering on acreage band happens downstream in the scoring engine — the
    LandSearch UI's size filter isn't reflected in URL params, so we pull
    pages unfiltered and let the criteria do the work.
    """

    name = "landsearch"

    def __init__(
        self,
        states: Iterable[str],
        *,
        config: LandSearchScraperConfig | None = None,
        page_fetcher=None,
    ):
        self.states = [s.upper() for s in states]
        self.config = config or LandSearchScraperConfig()
        self._page_fetcher = page_fetcher

    def fetch(self) -> Iterator[Listing]:
        fetch_page = self._page_fetcher or self._playwright_fetcher()
        try:
            for i, state in enumerate(self.states):
                if state not in _STATE_SLUG:
                    continue
                yield from self._fetch_state(state, fetch_page)
                if i < len(self.states) - 1:
                    # Cloudflare's challenge re-fires when the same browser
                    # session walks many pages; rebuild the session per state.
                    reset = getattr(fetch_page, "reset", None)
                    if callable(reset):
                        reset()
                    time.sleep(random.uniform(*self.config.state_delay_range))
        finally:
            close = getattr(fetch_page, "close", None)
            if callable(close):
                close()

    def _fetch_state(self, state: str, fetch_page) -> Iterator[Listing]:
        first_url = state_url(state, 1)
        first_html = fetch_page(first_url)
        if not first_html:
            return
        seen: set[str] = set()
        for listing in parse_state_html(first_html, state):
            if listing.listing_id in seen:
                continue
            seen.add(listing.listing_id)
            yield listing

        last_page = min(total_pages(first_html), self.config.max_pages_per_state)
        for page in range(2, last_page + 1):
            time.sleep(random.uniform(*self.config.page_delay_range))
            html = fetch_page(state_url(state, page))
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
