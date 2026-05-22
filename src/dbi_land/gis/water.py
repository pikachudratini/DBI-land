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

import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Sequence

from dbi_land.gis._distance import BBox, GeoFeature, load_features, nearest_distance_m
from dbi_land.models import Listing

DEFAULT_PERENNIAL_FCODES = (46006, 45800)
SPRING_FCODES = (45800,)


def _near_cache_path(
    path: str | Path, listing_bboxes: list[tuple[float, float, float, float]]
) -> Path:
    """Cache file for a stream-filter result, keyed by the listing bbox set
    plus the input file's size (so a different NHD file invalidates it)."""
    src = Path(path)
    size = src.stat().st_size if src.exists() else 0
    fp_src = repr((size, sorted(
        tuple(round(v, 4) for v in bb) for bb in listing_bboxes
    )))
    fingerprint = hashlib.sha1(fp_src.encode()).hexdigest()[:16]
    return Path(str(path) + f".near-{fingerprint}.geojson")


def _stream_load_near(
    path: str | Path,
    listing_bboxes: list[tuple[float, float, float, float]],
    *,
    fcode_field: str,
    keep_fcodes: tuple[int, ...],
) -> list[GeoFeature]:
    """Stream-parse a GeoJSON, keeping only features that fcode-match and
    whose bbox overlaps any listing bbox. Avoids json.loads on multi-GB files.

    The filtered subset is cached next to the input file, keyed by a
    fingerprint of the listing bbox set, so repeated runs over the same
    listings skip the (slow) full-file stream.
    """
    import ijson

    cache_path = _near_cache_path(path, listing_bboxes)
    if cache_path.exists():
        return load_features(cache_path)

    keep_set = set(int(c) for c in keep_fcodes)
    matched: list[dict] = []
    with open(path, "rb") as src:
        # use_float: ijson emits decimal.Decimal by default, which can't be
        # mixed with the float math in BBox.expand / nearest_distance_m.
        for feat in ijson.items(src, "features.item", use_float=True):
            props = feat.get("properties") or {}
            fc_val = props.get(fcode_field) or props.get(fcode_field.lower())
            if fc_val is not None:
                try:
                    if int(fc_val) not in keep_set:
                        continue
                except (TypeError, ValueError):
                    continue
            geom = feat.get("geometry") or {}
            gt = geom.get("type")
            coords = geom.get("coordinates") or []
            if gt == "LineString":
                pts = [c for c in coords if len(c) >= 2]
            elif gt == "MultiLineString":
                pts = [c for line in coords for c in line if len(c) >= 2]
            elif gt == "Point":
                pts = [coords] if len(coords) >= 2 else []
            elif gt == "MultiPoint":
                pts = [c for c in coords if len(c) >= 2]
            else:
                continue
            if not pts:
                continue
            lats = [p[1] for p in pts]
            lons = [p[0] for p in pts]
            fmin_lat, fmax_lat = min(lats), max(lats)
            fmin_lon, fmax_lon = min(lons), max(lons)
            for lmin_lat, lmax_lat, lmin_lon, lmax_lon in listing_bboxes:
                if (
                    fmax_lat < lmin_lat
                    or fmin_lat > lmax_lat
                    or fmax_lon < lmin_lon
                    or fmin_lon > lmax_lon
                ):
                    continue
                matched.append(feat)
                break

    cache_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": matched})
    )
    return load_features(cache_path)


def listings_to_bboxes(
    listings: Iterable["Listing"], buffer_m: float = 3000.0
) -> list[tuple[float, float, float, float]]:
    """Return (min_lat, max_lat, min_lon, max_lon) bboxes around each
    listing's coords, expanded by buffer_m on each side."""
    boxes: list[tuple[float, float, float, float]] = []
    lat_buf = buffer_m / 111_000.0
    for l in listings:
        if l.lat is None or l.lon is None:
            continue
        lon_buf = buffer_m / (111_000.0 * max(math.cos(math.radians(l.lat)), 1e-6))
        boxes.append((l.lat - lat_buf, l.lat + lat_buf, l.lon - lon_buf, l.lon + lon_buf))
    return boxes


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
        listing_bboxes: list[tuple[float, float, float, float]] | None = None,
    ) -> "WaterProximity":
        """Load and merge features from multiple GeoJSON files.

        Useful when perennial flowlines and spring points come from separate
        NHD layers (NHDFlowline vs NHDPoint), as is typical.

        When `listing_bboxes` is provided, the loader stream-parses each
        file with ijson and only keeps features whose bbox overlaps any
        listing bbox. This is required for NHD-scale GeoJSONs (multi-GB)
        that won't fit in RAM otherwise.
        """
        keep_set = set(int(c) for c in keep_fcodes)
        merged: list[GeoFeature] = []
        for p in paths:
            if listing_bboxes is not None:
                merged.extend(_stream_load_near(
                    p, listing_bboxes,
                    fcode_field=fcode_field, keep_fcodes=keep_fcodes,
                ))
                continue

            def keep(props: dict, _keep_set=keep_set, _field=fcode_field) -> bool:
                v = props.get(_field) or props.get(_field.lower())
                if v is None:
                    return True
                try:
                    return int(v) in _keep_set
                except (TypeError, ValueError):
                    return True

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
