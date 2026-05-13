"""USGS 3DEP elevation enrichment via the Elevation Point Query Service (EPQS).

EPQS returns ground elevation for a single (lon, lat) at 1-meter resolution
across CONUS where 3DEP coverage exists, falling back to coarser source data
elsewhere. The endpoint is rate-friendly but we still cache results on disk
keyed by rounded coordinates so reruns are free.

EPQS response shape (May 2026):
    {
      "location": {"x": -92.0, "y": 37.0, ...},
      "value": "354.69876",   # meters, string-encoded
      "resolution": 1
    }
Out-of-coverage points sometimes return value="-1000000" or no value at all.
We treat both as missing.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from dbi_land.models import Listing

_DEFAULT_BASE = "https://epqs.nationalmap.gov/v1/json"
_NODATA_SENTINEL = -1_000_000.0
_COORD_PRECISION = 5  # ~1.1m at the equator — enough to share cache between near-duplicate listings


@dataclass
class ElevationConfig:
    base_url: str = _DEFAULT_BASE
    rate_limit_s: float = 0.2
    timeout_s: float = 15.0

    @classmethod
    def from_env(cls) -> "ElevationConfig":
        return cls(
            base_url=os.environ.get("DBI_EPQS_URL", _DEFAULT_BASE),
            rate_limit_s=float(os.environ.get("DBI_EPQS_RATE", "0.2")),
        )


class ElevationEnricher:
    def __init__(
        self,
        cache_path: str | Path = "data/cache/elevation.json",
        config: ElevationConfig | None = None,
    ):
        self.cache_path = Path(cache_path)
        self.config = config or ElevationConfig()
        self._cache: dict[str, float | None] = {}
        if self.cache_path.exists():
            self._cache = json.loads(self.cache_path.read_text())
        self._last_request_at: float = 0.0

    @staticmethod
    def _key(lat: float, lon: float) -> str:
        return f"{round(lat, _COORD_PRECISION)},{round(lon, _COORD_PRECISION)}"

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache, sort_keys=True))

    def _wait(self) -> None:
        delta = time.monotonic() - self._last_request_at
        if delta < self.config.rate_limit_s:
            time.sleep(self.config.rate_limit_s - delta)

    def _query(self, lat: float, lon: float) -> float | None:
        params = {
            "x": lon,
            "y": lat,
            "units": "Meters",
            "wkid": 4326,
            "includeDate": "False",
        }
        url = f"{self.config.base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "dbi-land/0.1"})
        self._wait()
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            self._last_request_at = time.monotonic()
            return None
        self._last_request_at = time.monotonic()
        raw = data.get("value")
        if raw is None:
            return None
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return None
        if v <= _NODATA_SENTINEL + 1:
            return None
        return v

    def lookup(self, lat: float, lon: float) -> float | None:
        key = self._key(lat, lon)
        if key in self._cache:
            return self._cache[key]
        result = self._query(lat, lon)
        self._cache[key] = result
        self._save()
        return result

    def enrich(self, listings: Iterable[Listing]) -> list[Listing]:
        out: list[Listing] = []
        for l in listings:
            if l.lat is None or l.lon is None or "elevation_m" in l.extras:
                out.append(l)
                continue
            elev = self.lookup(l.lat, l.lon)
            if elev is None:
                out.append(l)
                continue
            new_extras = dict(l.extras)
            new_extras["elevation_m"] = round(elev, 1)
            out.append(replace(l, extras=new_extras))
        return out
