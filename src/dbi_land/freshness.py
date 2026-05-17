"""Track when each listing was last confirmed by a scrape.

`ListingStore.upsert` only writes brand-new keys, so we have no record of
which previously-stored listings were re-seen in the most recent scrape.
This module records that confirmation in a JSON index keyed by
"<source>:<listing_id>". Listings not refreshed within `max_stale_days`
are treated as inactive (sold, withdrawn, expired) and filtered before
scoring.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from dbi_land.models import Listing


def _key(listing: Listing) -> str:
    return f"{listing.source}:{listing.listing_id}"


class LastSeenIndex:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict[str, date] = {}
        if self.path.exists():
            raw = json.loads(self.path.read_text())
            for k, v in raw.items():
                try:
                    self._data[k] = date.fromisoformat(v)
                except (TypeError, ValueError):
                    continue

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {k: v.isoformat() for k, v in self._data.items()},
            sort_keys=True,
        ))

    def touch(
        self,
        listings: Iterable[Listing],
        *,
        when: date | None = None,
    ) -> int:
        """Mark these listings as just-confirmed. Returns count updated."""
        if when is None:
            when = date.today()
        count = 0
        for l in listings:
            self._data[_key(l)] = when
            count += 1
        if count:
            self._save()
        return count

    def last_seen(self, listing: Listing) -> date | None:
        return self._data.get(_key(listing))

    def filter_active(
        self,
        listings: Iterable[Listing],
        *,
        max_stale_days: int,
        today: date | None = None,
    ) -> tuple[list[Listing], int]:
        """Keep only listings refreshed within max_stale_days. Returns
        (active_listings, dropped_count). Listings with no last_seen entry
        are treated as stale and dropped."""
        if today is None:
            today = date.today()
        cutoff = today - timedelta(days=max_stale_days)
        active: list[Listing] = []
        dropped = 0
        for l in listings:
            ls = self._data.get(_key(l))
            if ls is None or ls < cutoff:
                dropped += 1
                continue
            active.append(l)
        return active, dropped
