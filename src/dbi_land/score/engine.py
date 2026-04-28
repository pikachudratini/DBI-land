from __future__ import annotations

from typing import Iterable

from dbi_land.config import Criteria
from dbi_land.models import Listing, ListingScore
from dbi_land.score.criteria import ALL_CRITERIA


class ScoringEngine:
    def __init__(self, criteria: Criteria):
        self.criteria = criteria

    def score(self, listing: Listing) -> ListingScore:
        crits = tuple(fn(listing, self.criteria) for fn in ALL_CRITERIA)
        return ListingScore(listing=listing, criteria=crits)


def score_listings(
    listings: Iterable[Listing],
    criteria: Criteria,
    *,
    only_passing: bool = True,
) -> list[ListingScore]:
    engine = ScoringEngine(criteria)
    scored = [engine.score(l) for l in listings]
    if only_passing:
        scored = [s for s in scored if s.passes]
    scored.sort(key=lambda s: s.total, reverse=True)
    return scored
