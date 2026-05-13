"""Cell-tower proximity scoring from an FCC-ASR style point GeoJSON.

The user does not want listings with a cell tower nearby (visual/EMF concerns).
Same closer-is-worse curve as the power-line module.

Source data: FCC Antenna Structure Registration (ASR) database. The public
extract is CSV; convert to a Point GeoJSON before feeding this module. A
minimal converter is provided as `TowerProximity.from_fcc_asr_csv`.

Score curve:
    distance <= min_setback_m  ->  hard fail (0.0)
    distance >= comfort_m      ->  best (1.0)
    in between                 ->  linear ramp from 0.05 to 1.0
"""
from __future__ import annotations

import csv
import math
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from dbi_land.gis._distance import BBox, GeoFeature, load_features, nearest_distance_m
from dbi_land.models import Listing


class TowerProximity:
    def __init__(
        self,
        features: list[GeoFeature],
        *,
        min_setback_m: float = 400.0,
        comfort_m: float = 3000.0,
    ):
        self.features = features
        self.min_setback_m = min_setback_m
        self.comfort_m = comfort_m

    @classmethod
    def from_geojson(
        cls,
        path: str | Path,
        *,
        status_field: str = "STATUS",
        keep_statuses: tuple[str, ...] = ("C", "CONSTRUCTED"),
        min_setback_m: float = 400.0,
        comfort_m: float = 3000.0,
    ) -> "TowerProximity":
        """Load constructed towers from a Point/MultiPoint GeoJSON.

        If a feature has no `status_field` we keep it (treat data as best-effort).
        """
        wanted = {s.upper() for s in keep_statuses}

        def keep(props: dict) -> bool:
            v = props.get(status_field)
            if v is None:
                return True
            return str(v).upper() in wanted

        features = load_features(path, keep=keep)
        return cls(features=features, min_setback_m=min_setback_m, comfort_m=comfort_m)

    @classmethod
    def from_fcc_asr_csv(
        cls,
        path: str | Path,
        *,
        lat_col: str = "LAT_DEG_TOTAL",
        lon_col: str = "LONG_DEG_TOTAL",
        status_col: str = "STATUS_CODE",
        keep_statuses: tuple[str, ...] = ("C",),
        min_setback_m: float = 400.0,
        comfort_m: float = 3000.0,
    ) -> "TowerProximity":
        """Load constructed towers from a flat FCC-ASR style CSV.

        FCC's published ASR extract uses pipe-delimited records — set the reader
        dialect upstream if needed; this loader autodetects comma vs pipe.
        """
        wanted = {s.upper() for s in keep_statuses}
        text = Path(path).read_text()
        sample = text[:4096]
        delim = "|" if sample.count("|") > sample.count(",") else ","
        features: list[GeoFeature] = []
        reader = csv.DictReader(text.splitlines(), delimiter=delim)
        for row in reader:
            status = (row.get(status_col) or "").strip().upper()
            if status and status not in wanted:
                continue
            try:
                lat = float(row[lat_col])
                lon = float(row[lon_col])
            except (KeyError, TypeError, ValueError):
                continue
            features.append(GeoFeature(
                bbox=BBox(lat, lon, lat, lon),
                kind="point",
                vertices=[(lon, lat)],
            ))
        return cls(features=features, min_setback_m=min_setback_m, comfort_m=comfort_m)

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


def score_tower_proximity(listings: Iterable[Listing], tp: TowerProximity) -> list[Listing]:
    out: list[Listing] = []
    for l in listings:
        if l.lat is None or l.lon is None:
            out.append(l)
            continue
        s, d = tp.score(l.lat, l.lon)
        new_extras = dict(l.extras)
        new_extras["tower_proximity_score"] = s
        new_extras["tower_distance_m"] = round(d, 1) if not math.isinf(d) else None
        out.append(replace(l, extras=new_extras))
    return out
