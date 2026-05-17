"""Water-feature proximity scoring from NHD-style GeoJSON.

The buyer values land with year-round water access (creeks, rivers, springs).
Inverse score curve from the power module: closer is better.

Score curve:
    distance <= ideal_m   ->  best (1.0)
    distance >= max_m     ->  hard fail (0.0)
    in between            ->  linear ramp

NHD FCode reference (a few of the most useful):
    46006  perennial stream/river   (line, NHDFlowline)
    46003  intermittent stream      (line, NHDFlowline)
    46007  ephemeral stream         (line, NHDFlowline)
    45800  spring / seep            (point, NHDPoint)
    55800  artificial path          (line)
Defaults keep perennial flowlines and springs — the two year-round sources the
buyer cares about.
"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Sequence

from dbi_land.gis._distance import GeoFeature, load_features, nearest_distance_m
from dbi_land.models import Listing

DEFAULT_PERENNIAL_FCODES = (46006, 45800)
SPRING_FCODES = (45800,)


class WaterProximity:
    def __init__(
        self,
        features: list[GeoFeature],
        *,
        ideal_m: float = 200.0,
        max_m: float = 3000.0,
    ):
        self.features = features
        self.ideal_m = ideal_m
        self.max_m = max_m

    @classmethod
    def from_geojson(
        cls,
        path: str | Path,
        *,
        fcode_field: str = "FCODE",
        keep_fcodes: tuple[int, ...] = DEFAULT_PERENNIAL_FCODES,
        ideal_m: float = 200.0,
        max_m: float = 3000.0,
    ) -> "WaterProximity":
        keep_set = set(int(c) for c in keep_fcodes)

        def keep(props: dict) -> bool:
            v = props.get(fcode_field)
            if v is None:
                return True
            try:
                return int(v) in keep_set
            except (TypeError, ValueError):
                return True

        features = load_features(path, keep=keep)
        return cls(features=features, ideal_m=ideal_m, max_m=max_m)

    @classmethod
    def from_paths(
        cls,
        paths: Sequence[str | Path],
        *,
        fcode_field: str = "FCODE",
        keep_fcodes: tuple[int, ...] = DEFAULT_PERENNIAL_FCODES,
        ideal_m: float = 200.0,
        max_m: float = 3000.0,
    ) -> "WaterProximity":
        """Load and merge features from multiple GeoJSON files.

        Useful when perennial flowlines and spring points come from separate
        NHD layers (NHDFlowline vs NHDPoint), as is typical.
        """
        keep_set = set(int(c) for c in keep_fcodes)

        def keep(props: dict) -> bool:
            v = props.get(fcode_field)
            if v is None:
                return True
            try:
                return int(v) in keep_set
            except (TypeError, ValueError):
                return True

        merged: list[GeoFeature] = []
        for p in paths:
            merged.extend(load_features(p, keep=keep))
        return cls(features=merged, ideal_m=ideal_m, max_m=max_m)

    def distance_m(self, lat: float, lon: float) -> float:
        return nearest_distance_m(
            lat, lon, self.features,
            max_search_m=self.max_m,
            early_stop_m=self.ideal_m,
        )

    def score(self, lat: float, lon: float) -> tuple[float, float]:
        d = self.distance_m(lat, lon)
        if math.isinf(d) or d >= self.max_m:
            return 0.0, d
        if d <= self.ideal_m:
            return 1.0, d
        span = self.max_m - self.ideal_m
        ramp = 1.0 - (d - self.ideal_m) / span
        return max(0.0, min(1.0, ramp)), d


def score_water_proximity(listings: Iterable[Listing], wp: WaterProximity) -> list[Listing]:
    out: list[Listing] = []
    for l in listings:
        if l.lat is None or l.lon is None:
            out.append(l)
            continue
        s, d = wp.score(l.lat, l.lon)
        new_extras = dict(l.extras)
        new_extras["water_score"] = s
        new_extras["water_distance_m"] = round(d, 1) if not math.isinf(d) else None
        out.append(replace(l, extras=new_extras))
    return out
