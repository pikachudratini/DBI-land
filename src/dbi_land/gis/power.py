"""Power-line proximity scoring from a HIFLD-style GeoJSON of transmission lines.

Score curve:
    distance <= min_setback_m  ->  hard fail (0.0)
    distance >= comfort_m      ->  best (1.0)
    in between                 ->  linear ramp from 0.05 to 1.0
"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from dbi_land.gis._distance import GeoFeature, load_features, nearest_distance_m
from dbi_land.models import Listing


class PowerProximity:
    def __init__(
        self,
        features: list[GeoFeature],
        *,
        min_voltage_kv: float = 69.0,
        min_setback_m: float = 100.0,
        comfort_m: float = 1500.0,
    ):
        self.features = features
        self.min_voltage_kv = min_voltage_kv
        self.min_setback_m = min_setback_m
        self.comfort_m = comfort_m

    @classmethod
    def from_geojson(
        cls,
        path: str | Path,
        *,
        voltage_field: str = "VOLTAGE",
        min_voltage_kv: float = 69.0,
        min_setback_m: float = 100.0,
        comfort_m: float = 1500.0,
    ) -> "PowerProximity":
        def keep(props: dict) -> bool:
            v = props.get(voltage_field)
            try:
                return v is None or float(v) >= min_voltage_kv
            except (TypeError, ValueError):
                return True

        features = load_features(path, keep=keep)
        return cls(
            features=features,
            min_voltage_kv=min_voltage_kv,
            min_setback_m=min_setback_m,
            comfort_m=comfort_m,
        )

    def distance_m(self, lat: float, lon: float) -> float:
        return nearest_distance_m(
            lat, lon, self.features,
            max_search_m=self.comfort_m,
            early_stop_m=self.min_setback_m,
        )

    def score(self, lat: float, lon: float) -> tuple[float, float]:
        d = self.distance_m(lat, lon)
        if math.isinf(d):
            return 1.0, d
        if d <= self.min_setback_m:
            return 0.0, d
        if d >= self.comfort_m:
            return 1.0, d
        span = self.comfort_m - self.min_setback_m
        ramp = (d - self.min_setback_m) / span
        return max(0.05, min(1.0, ramp)), d


def score_power_proximity(listings: Iterable[Listing], pp: PowerProximity) -> list[Listing]:
    out: list[Listing] = []
    for l in listings:
        if l.lat is None or l.lon is None:
            out.append(l)
            continue
        s, d = pp.score(l.lat, l.lon)
        new_extras = dict(l.extras)
        new_extras["power_proximity_score"] = s
        new_extras["power_distance_m"] = round(d, 1) if not math.isinf(d) else None
        out.append(replace(l, extras=new_extras))
    return out
