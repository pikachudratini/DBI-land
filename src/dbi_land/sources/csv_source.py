from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from dbi_land.models import Listing


def _parse_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(value: str) -> float | None:
    value = value.strip().replace(",", "").replace("$", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class CsvSource:
    """Load listings from a CSV file the user maintains.

    Required columns: listing_id, url, state, acres, price_usd
    Optional: county, lat, lon, title, description, listed_on, source
    """

    name = "csv"

    REQUIRED = ("listing_id", "url", "state", "acres", "price_usd")

    def __init__(self, path: str | Path, *, source_label: str | None = None):
        self.path = Path(path)
        self.source_label = source_label or self.path.stem

    def fetch(self) -> Iterable[Listing]:
        with self.path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = [c for c in self.REQUIRED if c not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"CSV {self.path} is missing required columns: {missing}")
            for row in reader:
                acres = _parse_float(row["acres"])
                price = _parse_float(row["price_usd"])
                if acres is None or price is None:
                    continue
                lat = _parse_float(row.get("lat", ""))
                lon = _parse_float(row.get("lon", ""))
                yield Listing(
                    listing_id=row["listing_id"].strip(),
                    source=row.get("source", "").strip() or self.source_label,
                    url=row["url"].strip(),
                    state=row["state"].strip().upper(),
                    county=(row.get("county") or "").strip() or None,
                    acres=acres,
                    price_usd=price,
                    lat=lat,
                    lon=lon,
                    title=(row.get("title") or "").strip(),
                    description=(row.get("description") or "").strip(),
                    listed_on=_parse_date(row.get("listed_on", "")),
                )
