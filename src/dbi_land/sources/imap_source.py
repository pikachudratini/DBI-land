"""IMAP-backed listing source.

Reads alert emails (LandSearch, LandWatch, Lands of America, etc.) from a
configured mailbox/folder and extracts listings. Default behavior is
non-destructive: messages are searched read-only, the JSONL store dedupes
across runs.
"""
from __future__ import annotations

import email
import imaplib
import os
import re
from dataclasses import dataclass
from email.message import Message
from typing import Iterable, Iterator
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from dbi_land.models import Listing

# Heuristic regexes; defensive about the wide format variation across senders.
_ACRES_RE = re.compile(r"(\d{1,3}(?:[,\d]{0,4})(?:\.\d+)?)\s*(?:ac\b|acres?\b)", re.I)
_PRICE_RE = re.compile(r"\$\s?([0-9][0-9,]*)(?:\.\d+)?")
_STATE_RE = re.compile(r"\b([A-Z]{2})\b")
_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}

# Hostnames whose links are listing pages we want to capture.
_LISTING_HOSTS = (
    "landsearch.com",
    "landwatch.com",
    "landsofamerica.com",
    "landflip.com",
    "landandfarm.com",
    "land.com",
)


@dataclass(frozen=True)
class _Block:
    text: str
    url: str
    source: str


def _host_to_source(host: str) -> str:
    h = host.lower().lstrip(".")
    if h.startswith("www."):
        h = h[4:]
    for known in _LISTING_HOSTS:
        if h == known or h.endswith("." + known):
            return known.split(".")[0]
    return h.split(".")[0] or "email"


def _extract_blocks(html: str) -> list[_Block]:
    """Walk the DOM, anchor on listing-host links, and capture surrounding text.

    Strategy: for each <a href> pointing at a known listing host, gather the
    text from its nearest container (parent block element) which usually holds
    the listing's price + acreage + location callout in alert emails.
    """
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[_Block] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        try:
            host = urlparse(href).hostname or ""
        except ValueError:
            continue
        source = _host_to_source(host)
        if source not in {h.split(".")[0] for h in _LISTING_HOSTS}:
            continue
        if href in seen:
            continue
        seen.add(href)
        container = a
        for _ in range(4):
            if container.parent is None:
                break
            container = container.parent
            if container.name in {"tr", "td", "table", "div", "li"}:
                break
        text = container.get_text(" ", strip=True)
        blocks.append(_Block(text=text, url=href, source=source))
    return blocks


def _extract_text_blocks(text: str) -> list[_Block]:
    """Plain-text fallback: split on URLs and emit one block per listing URL."""
    urls = re.findall(r"https?://[^\s>\)]+", text)
    blocks: list[_Block] = []
    seen: set[str] = set()
    for url in urls:
        host = urlparse(url).hostname or ""
        source = _host_to_source(host)
        if source not in {h.split(".")[0] for h in _LISTING_HOSTS}:
            continue
        if url in seen:
            continue
        seen.add(url)
        # take ±200 chars around the URL as the block context
        idx = text.find(url)
        start = max(0, idx - 200)
        end = min(len(text), idx + len(url) + 200)
        blocks.append(_Block(text=text[start:end], url=url, source=source))
    return blocks


def _largest_number(matches: Iterable[re.Match]) -> float | None:
    best: float | None = None
    for m in matches:
        try:
            v = float(m.group(1).replace(",", ""))
        except (ValueError, IndexError):
            continue
        if best is None or v > best:
            best = v
    return best


def _parse_state(text: str) -> str | None:
    lower = text.lower()
    for name, code in _STATE_NAMES.items():
        if name in lower:
            return code
    m = _STATE_RE.search(text)
    return m.group(1) if m else None


def _listing_id_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else url


def parse_email(msg: Message) -> Iterator[Listing]:
    """Yield Listings extracted from a single email Message."""
    html_part: str | None = None
    text_part: str | None = None
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype == "text/html" and html_part is None:
            html_part = part.get_payload(decode=True).decode(
                part.get_content_charset() or "utf-8", errors="replace"
            )
        elif ctype == "text/plain" and text_part is None:
            text_part = part.get_payload(decode=True).decode(
                part.get_content_charset() or "utf-8", errors="replace"
            )

    blocks: list[_Block] = []
    if html_part:
        blocks = _extract_blocks(html_part)
    if not blocks and text_part:
        blocks = _extract_text_blocks(text_part)

    for b in blocks:
        acres = _largest_number(_ACRES_RE.finditer(b.text))
        price = _largest_number(_PRICE_RE.finditer(b.text))
        state = _parse_state(b.text)
        if acres is None or price is None or state is None:
            continue
        yield Listing(
            listing_id=_listing_id_from_url(b.url),
            source=b.source,
            url=b.url,
            state=state,
            county=None,
            acres=acres,
            price_usd=price,
            lat=None,
            lon=None,
            title=b.text[:120].strip(),
        )


@dataclass
class ImapConfig:
    host: str
    user: str
    password: str
    folder: str = "INBOX"
    search: str = '(UNSEEN FROM "landsearch")'
    use_ssl: bool = True
    port: int | None = None
    mark_seen: bool = False

    @classmethod
    def from_env(cls, prefix: str = "DBI_IMAP_") -> "ImapConfig":
        return cls(
            host=os.environ[f"{prefix}HOST"],
            user=os.environ[f"{prefix}USER"],
            password=os.environ[f"{prefix}PASSWORD"],
            folder=os.environ.get(f"{prefix}FOLDER", "INBOX"),
            search=os.environ.get(f"{prefix}SEARCH", '(UNSEEN FROM "landsearch")'),
            use_ssl=os.environ.get(f"{prefix}SSL", "1") not in {"0", "false", "False"},
            port=int(os.environ[f"{prefix}PORT"]) if f"{prefix}PORT" in os.environ else None,
            mark_seen=os.environ.get(f"{prefix}MARK_SEEN", "0") not in {"0", "false", "False"},
        )


class ImapSource:
    name = "imap"

    def __init__(self, config: ImapConfig):
        self.config = config

    def fetch(self) -> Iterable[Listing]:
        cfg = self.config
        cls = imaplib.IMAP4_SSL if cfg.use_ssl else imaplib.IMAP4
        client = cls(cfg.host, cfg.port) if cfg.port else cls(cfg.host)
        try:
            client.login(cfg.user, cfg.password)
            client.select(cfg.folder, readonly=not cfg.mark_seen)
            typ, data = client.search(None, cfg.search)
            if typ != "OK":
                return
            for num in data[0].split():
                typ, msg_data = client.fetch(num, "(RFC822)")
                if typ != "OK" or not msg_data:
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                yield from parse_email(msg)
                if cfg.mark_seen:
                    client.store(num, "+FLAGS", "\\Seen")
        finally:
            try:
                client.close()
            except Exception:
                pass
            client.logout()
