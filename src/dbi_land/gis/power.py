"""Power-line proximity scoring from a HIFLD-style GeoJSON of transmission lines.

Pure-Python: no GDAL / shapely / geopandas dependency. Distance is computed
as haversine point-to-vertex over densified line geometry; for transmission
lines with the typical 50–200 m vertex spacing in HIFLD this is within a few
percent of true point-to-segment distance — accurate enough for the
"is the listing close to power" decision boundaries we score against.

Score curve:
    distance <= min_setback_m  ->  hard fail (0.0)  (e.g., line crosses parcel)
    distance >= comfort_m      ->  best (1.0)
    in between                 ->  linear ramp from 0.05 to 1.0

The score writes onto Listing.extras["power_proximity_score"] so the
existing `score_access` criterion picks it up.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from dbi_land.models import Listing

EARTH_RADIUS_M = 6_371_008.8


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _point_segment_m(
    lat0: float, lon0: float,
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """Distance in meters from point (lat0, lon0) to segment defined by two endpoints.

    Uses an equirectangular projection centered at the query point. Distortion
    is negligible at segment lengths typical for transmission-line vertices
    (<=~1 km) anywhere outside the polar regions.
    """
    cos_lat = math.cos(math.radians(lat0))
    mx_per_deg_lon = (math.pi / 180.0) * EARTH_RADIUS_M * cos_lat
    m_per_deg_lat = (math.pi / 180.0) * EARTH_RADIUS_M
    px = (lon0 - lon0) * mx_per_deg_lon  # 0
    py = (lat0 - lat0) * m_per_deg_lat   # 0
    ax = (lon1 - lon0) * mx_per_deg_lon
    ay = (lat1 - lat0) * m_per_deg_lat
    bx = (lon2 - lon0) * mx_per_deg_lon
    by = (lat2 - lat0) * m_per_deg_lat
    abx, aby = bx - ax, by - ay
    seg_len_sq = abx * abx + aby * aby
    if seg_len_sq <= 0.0:
        return math.hypot(ax - px, ay - py)
    t = ((px - ax) * abx + (py - ay) * aby) / seg_len_sq
    t = max(0.0, min(1.0, t))
    cx = ax + t * abx
    cy = ay + t * aby
    return math.hypot(cx - px, cy - py)


def _iter_line_vertices(geom: dict) -> Iterable[tuple[float, float]]:
    """Yield (lon, lat) tuples from a GeoJSON LineString or MultiLineString."""
    t = geom.get("type")
    coords = geom.get("coordinates", [])
    if t == "LineString":
        for c in coords:
            yield c[0], c[1]
    elif t == "MultiLineString":
        for line in coords:
            for c in line:
                yield c[0], c[1]


@dataclass(frozen=True)
class _BBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def expand(self, deg: float) -> "_BBox":
        return _BBox(
            self.min_lat - deg,
            self.min_lon - deg,
            self.max_lat + deg,
            self.max_lon + deg,
        )

    def contains(self, lat: float, lon: float) -> bool:
        return (
            self.min_lat <= lat <= self.max_lat
            and self.min_lon <= lon <= self.max_lon
        )


@dataclass
class _Feature:
    bbox: _BBox
    vertices: list[tuple[float, float]]  # (lon, lat)
    voltage_kv: float | None


class PowerProximity:
    def __init__(
        self,
        features: list[_Feature],
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
        data = json.loads(Path(path).read_text())
        features: list[_Feature] = []
        for feat in data.get("features", []):
            geom = feat.get("geometry") or {}
            verts = list(_iter_line_vertices(geom))
            if not verts:
                continue
            props = feat.get("properties") or {}
            v = props.get(voltage_field)
            try:
                voltage_kv = float(v) if v is not None else None
            except (TypeError, ValueError):
                voltage_kv = None
            if voltage_kv is not None and voltage_kv < min_voltage_kv:
                continue
            lats = [lat for _, lat in verts]
            lons = [lon for lon, _ in verts]
            bbox = _BBox(min(lats), min(lons), max(lats), max(lons))
            features.append(_Feature(bbox=bbox, vertices=verts, voltage_kv=voltage_kv))
        return cls(
            features=features,
            min_voltage_kv=min_voltage_kv,
            min_setback_m=min_setback_m,
            comfort_m=comfort_m,
        )

    def distance_m(self, lat: float, lon: float) -> float:
        # Pre-filter by bounding box expanded by comfort_m converted to deg.
        # 1 deg lat ≈ 111_111 m; lon shrinks by cos(lat). Use lat for both as
        # a conservative over-estimate.
        deg = self.comfort_m / 100_000.0
        best = math.inf
        for feat in self.features:
            if not feat.bbox.expand(deg).contains(lat, lon):
                continue
            verts = feat.vertices
            for i in range(len(verts) - 1):
                lon1, lat1 = verts[i]
                lon2, lat2 = verts[i + 1]
                d = _point_segment_m(lat, lon, lat1, lon1, lat2, lon2)
                if d < best:
                    best = d
                    if best <= self.min_setback_m:
                        return best
            if len(verts) == 1:
                vlon, vlat = verts[0]
                d = _haversine_m(lat, lon, vlat, vlon)
                if d < best:
                    best = d
        return best

    def score(self, lat: float, lon: float) -> tuple[float, float]:
        """Return (score, distance_m). distance_m is inf if no nearby lines."""
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
    """Annotate listings with extras['power_proximity_score'] and return a new list."""
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
