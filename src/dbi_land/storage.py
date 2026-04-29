"""Append-only JSONL storage of seen listings, keyed by (source, listing_id)."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from dbi_land.models import Listing


def _serialize(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(f"not serializable: {type(o)}")


def _key(listing: Listing) -> str:
    return f"{listing.source}:{listing.listing_id}"


class ListingStore:
    """Persistent dedupe store. One listing per line; last write wins on key."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _read_all(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        rows: dict[str, dict] = {}
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                rows[f"{obj['source']}:{obj['listing_id']}"] = obj
        return rows

    def known_keys(self) -> set[str]:
        return set(self._read_all().keys())

    def upsert(self, listings: Iterable[Listing]) -> list[Listing]:
        """Append listings whose keys aren't already stored. Returns the new ones."""
        known = self.known_keys()
        new: list[Listing] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            for l in listings:
                if _key(l) in known:
                    continue
                f.write(json.dumps(asdict(l), default=_serialize) + "\n")
                known.add(_key(l))
                new.append(l)
        return new

    def all_listings(self) -> list[Listing]:
        rows = self._read_all().values()
        out: list[Listing] = []
        for r in rows:
            listed = r.get("listed_on")
            if isinstance(listed, str):
                try:
                    listed = date.fromisoformat(listed)
                except ValueError:
                    listed = None
            out.append(
                Listing(
                    listing_id=r["listing_id"],
                    source=r["source"],
                    url=r["url"],
                    state=r["state"],
                    county=r.get("county"),
                    acres=r["acres"],
                    price_usd=r["price_usd"],
                    lat=r.get("lat"),
                    lon=r.get("lon"),
                    title=r.get("title", ""),
                    description=r.get("description", ""),
                    listed_on=listed,
                    extras=r.get("extras", {}) or {},
                )
            )
        return out
