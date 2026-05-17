"""Cross-source listing dedupe.

LandSearch, LandWatch, and Land and Farm frequently republish the same MLS
parcel under different internal IDs. The storage layer dedupes by
(source, listing_id), which catches re-fetches of the same site but not
the same parcel appearing on multiple sites. This module collapses those
cross-source duplicates before scoring.

Fingerprint: (state, normalized county, acres, price_usd). Anything matching
all four is treated as the same parcel. Representative wins by metadata
completeness (lat/lon, county, title, listed_on); ties break alphabetically
by source so output is stable.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from dbi_land.models import Listing


def _county_key(county: str | None) -> str:
    return (county or "").strip().lower()


def _fingerprint(listing: Listing) -> tuple[str, str, float, float]:
    return (listing.state, _county_key(listing.county), listing.acres, listing.price_usd)


def _metadata_richness(listing: Listing) -> int:
    """How many useful optional fields are populated. Higher = better representative."""
    score = 0
    if listing.lat is not None:
        score += 1
    if listing.lon is not None:
        score += 1
    if listing.county:
        score += 1
    if listing.title:
        score += 1
    if listing.listed_on is not None:
        score += 1
    return score


def _pick_representative(group: list[Listing]) -> Listing:
    # Highest metadata richness wins; tiebreak by source name (stable).
    return max(group, key=lambda l: (_metadata_richness(l), -ord(l.source[0]) if l.source else 0))


def dedupe_cross_source(listings: Iterable[Listing]) -> tuple[list[Listing], int]:
    """Collapse listings sharing (state, county, acres, price) across sources.

    Returns (deduped_listings, dropped_count). Order of survivors follows
    first-appearance of each fingerprint, which keeps downstream output
    deterministic regardless of which source loaded first.
    """
    groups: dict[tuple, list[Listing]] = defaultdict(list)
    order: list[tuple] = []
    for l in listings:
        key = _fingerprint(l)
        if key not in groups:
            order.append(key)
        groups[key].append(l)

    survivors: list[Listing] = []
    dropped = 0
    for key in order:
        group = groups[key]
        if len(group) == 1:
            survivors.append(group[0])
        else:
            survivors.append(_pick_representative(group))
            dropped += len(group) - 1
    return survivors, dropped
