from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Listing:
    listing_id: str
    source: str
    url: str
    state: str
    county: Optional[str]
    acres: float
    price_usd: float
    lat: Optional[float]
    lon: Optional[float]
    title: str = ""
    description: str = ""
    listed_on: Optional[date] = None
    extras: dict = field(default_factory=dict)

    @property
    def price_per_acre(self) -> float:
        if self.acres <= 0:
            return float("inf")
        return self.price_usd / self.acres


@dataclass(frozen=True)
class CriterionScore:
    name: str
    score: float
    weight: float
    detail: str = ""

    @property
    def weighted(self) -> float:
        return self.score * self.weight


@dataclass(frozen=True)
class ListingScore:
    listing: Listing
    criteria: tuple[CriterionScore, ...]

    @property
    def total(self) -> float:
        total_weight = sum(c.weight for c in self.criteria) or 1.0
        return sum(c.weighted for c in self.criteria) / total_weight

    @property
    def passes(self) -> bool:
        return all(c.score > 0 for c in self.criteria)
