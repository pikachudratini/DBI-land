"""Scoring functions for the five MVP criteria.

Each function returns a value in [0, 1]. A score of 0 means the criterion is
violated (hard fail); higher is better. Heavy GIS-based criteria (water, road,
power) are stubbed with neutral 0.5 scores until the GIS modules land in
Week 2 — they read optional `extras` fields on the Listing if pre-computed
externally.
"""
from __future__ import annotations

from dbi_land.config import Criteria
from dbi_land.models import CriterionScore, Listing


def score_state(listing: Listing, criteria: Criteria) -> CriterionScore:
    weight = criteria.weight("state", 1.0)
    in_states = listing.state in criteria.states
    excluded = listing.county and any(
        ec.lower() == listing.county.lower() for ec in criteria.excluded_counties
    )
    if not in_states or excluded:
        return CriterionScore(
            "state", 0.0, weight, f"{listing.state}/{listing.county} not in target list"
        )
    return CriterionScore("state", 1.0, weight, f"{listing.state} matches")


def score_acreage(listing: Listing, criteria: Criteria) -> CriterionScore:
    weight = criteria.weight("acreage", 1.0)
    acres = listing.acres
    if acres > criteria.sanity_max_acres:
        return CriterionScore(
            "acreage", 0.0, weight,
            f"{acres} ac exceeds sanity cap {criteria.sanity_max_acres:.0f} (likely bad data)",
        )
    band = criteria.best_band(acres)
    if band is None:
        # Above the top band but below sanity cap → score as top-band quality.
        # Buyer prefers larger parcels, so don't silently drop legit big ranches.
        top = max(criteria.acreage_bands, key=lambda b: b.max_acres)
        if acres > top.max_acres:
            return CriterionScore(
                "acreage", min(top.weight, 1.0), weight,
                f"{acres} ac above top band ({top.min_acres}-{top.max_acres})",
            )
        return CriterionScore(
            "acreage", 0.0, weight, f"{acres} ac below smallest band"
        )
    span = max(band.max_acres - band.min_acres, 1.0)
    midpoint = (band.min_acres + band.max_acres) / 2.0
    distance_from_mid = abs(acres - midpoint) / (span / 2.0)
    score = max(0.0, 1.0 - 0.4 * distance_from_mid) * band.weight
    return CriterionScore(
        "acreage", min(score, 1.0), weight, f"{acres} ac in band {band.min_acres}-{band.max_acres}"
    )


def score_price(listing: Listing, criteria: Criteria) -> CriterionScore:
    weight = criteria.weight("price", 1.0)
    ppa = listing.price_per_acre
    cap_ppa = criteria.price.max_price_per_acre
    cap_total = criteria.price.max_total_price
    # Reject scraped placeholders ("Call for Price" → price_usd=1.0 etc.).
    # No legitimate parcel asks under $1000; treat as unknown-price → hard fail
    # so call-for-price listings don't rank #1 with $0/ac.
    if listing.price_usd < 1000:
        return CriterionScore(
            "price", 0.0, weight, f"${listing.price_usd:,.0f} not a real list price"
        )
    if listing.price_usd > cap_total or ppa > cap_ppa:
        return CriterionScore(
            "price", 0.0, weight, f"${ppa:,.0f}/ac total ${listing.price_usd:,.0f} exceeds cap"
        )
    headroom = 1.0 - (ppa / cap_ppa)
    return CriterionScore("price", max(0.05, headroom), weight, f"${ppa:,.0f}/ac")


def _extras_score(listing: Listing, key: str) -> float | None:
    val = listing.extras.get(key)
    if val is None:
        return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, v))


def score_water(listing: Listing, criteria: Criteria) -> CriterionScore:
    weight = criteria.weight("water", 1.0)
    s = _extras_score(listing, "water_score")
    if s is None:
        return CriterionScore("water", 0.5, weight, "no GIS data; neutral")
    if s < criteria.min_water_score:
        return CriterionScore("water", 0.0, weight, f"{s:.2f} below floor")
    return CriterionScore("water", s, weight, f"{s:.2f}")


def score_access(listing: Listing, criteria: Criteria) -> CriterionScore:
    """Combined road access + power/tower proximity, all from optional extras."""
    weight = criteria.weight("access", 1.0)
    road = _extras_score(listing, "road_access_score")
    power = _extras_score(listing, "power_proximity_score")
    tower = _extras_score(listing, "tower_proximity_score")
    parts = []
    components: list[float] = []
    if road is not None:
        if road < criteria.min_road_access_score:
            return CriterionScore("access", 0.0, weight, f"road {road:.2f} below floor")
        components.append(road)
        parts.append(f"road {road:.2f}")
    if power is not None:
        if power < criteria.min_power_proximity_score:
            return CriterionScore("access", 0.0, weight, f"power {power:.2f} below floor")
        components.append(power)
        parts.append(f"power {power:.2f}")
    if tower is not None:
        if tower < criteria.min_tower_proximity_score:
            return CriterionScore("access", 0.0, weight, f"tower {tower:.2f} below floor")
        components.append(tower)
        parts.append(f"tower {tower:.2f}")
    if not components:
        return CriterionScore("access", 0.5, weight, "no GIS data; neutral")
    avg = sum(components) / len(components)
    return CriterionScore("access", avg, weight, ", ".join(parts))


ALL_CRITERIA = (score_state, score_acreage, score_price, score_water, score_access)
