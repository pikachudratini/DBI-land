"""Nominatim-based geocoder with on-disk JSON cache and polite rate-limiting.

Use only for listings that arrive without coordinates. Nominatim's usage
policy requires a custom User-Agent and a maximum of 1 request/second; we
respect both. Configure your contact via DBI_NOMINATIM_CONTACT.
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

_DEFAULT_BASE = "https://nominatim.openstreetmap.org/search"


@dataclass
class GeocoderConfig:
    base_url: str = _DEFAULT_BASE
    contact: str = "anonymous"
    rate_limit_s: float = 1.05
    timeout_s: float = 15.0

    @classmethod
    def from_env(cls) -> "GeocoderConfig":
        return cls(
            base_url=os.environ.get("DBI_NOMINATIM_URL", _DEFAULT_BASE),
            contact=os.environ.get("DBI_NOMINATIM_CONTACT", "anonymous"),
            rate_limit_s=float(os.environ.get("DBI_NOMINATIM_RATE", "1.05")),
        )


class Geocoder:
    def __init__(
        self,
        cache_path: str | Path = "data/cache/geocode.json",
        config: GeocoderConfig | None = None,
    ):
        self.cache_path = Path(cache_path)
        self.config = config or GeocoderConfig()
        self._cache: dict[str, tuple[float, float] | None] = {}
        if self.cache_path.exists():
            self._cache = {
                k: (tuple(v) if v is not None else None)
                for k, v in json.loads(self.cache_path.read_text()).items()
            }
        self._last_request_at: float = 0.0

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache, sort_keys=True))

    def _wait(self) -> None:
        delta = time.monotonic() - self._last_request_at
        if delta < self.config.rate_limit_s:
            time.sleep(self.config.rate_limit_s - delta)

    def _query(self, q: str) -> tuple[float, float] | None:
        params = {"q": q, "format": "json", "limit": 1, "countrycodes": "us"}
        url = f"{self.config.base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"dbi-land/0.1 ({self.config.contact})"},
        )
        self._wait()
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            self._last_request_at = time.monotonic()
            return None
        self._last_request_at = time.monotonic()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"])

    def geocode(self, query: str) -> tuple[float, float] | None:
        if query in self._cache:
            return self._cache[query]
        result = self._query(query)
        self._cache[query] = result
        self._save()
        return result

    def enrich(self, listings: Iterable[Listing]) -> list[Listing]:
        out: list[Listing] = []
        for l in listings:
            if l.lat is not None and l.lon is not None:
                out.append(l)
                continue
            q = ", ".join(p for p in (l.county, l.state, "USA") if p)
            if not q.strip(", "):
                out.append(l)
                continue
            coords = self.geocode(q)
            if coords is None:
                out.append(l)
                continue
            lat, lon = coords
            out.append(replace(l, lat=lat, lon=lon))
        return out
