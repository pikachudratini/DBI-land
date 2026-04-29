"""Shared distance utilities for GIS feature-proximity scoring.

Pure-Python: no GDAL / shapely. Distances are computed via a local
equirectangular projection centered on the query point, accurate to within a
few percent for the segment lengths typical in HIFLD / NHD line vector data.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

EARTH_RADIUS_M = 6_371_008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def point_segment_m(
    lat0: float, lon0: float,
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    cos_lat = math.cos(math.radians(lat0))
    mx_per_deg_lon = (math.pi / 180.0) * EARTH_RADIUS_M * cos_lat
    m_per_deg_lat = (math.pi / 180.0) * EARTH_RADIUS_M
    ax = (lon1 - lon0) * mx_per_deg_lon
    ay = (lat1 - lat0) * m_per_deg_lat
    bx = (lon2 - lon0) * mx_per_deg_lon
    by = (lat2 - lat0) * m_per_deg_lat
    abx, aby = bx - ax, by - ay
    seg_len_sq = abx * abx + aby * aby
    if seg_len_sq <= 0.0:
        return math.hypot(ax, ay)
    t = (-ax * abx + -ay * aby) / seg_len_sq
    t = max(0.0, min(1.0, t))
    cx = ax + t * abx
    cy = ay + t * aby
    return math.hypot(cx, cy)


@dataclass(frozen=True)
class BBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def expand(self, deg: float) -> "BBox":
        return BBox(
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
class GeoFeature:
    bbox: BBox
    kind: str  # "point" or "line"
    vertices: list[tuple[float, float]]  # (lon, lat)


def _iter_points(geom: dict) -> Iterable[tuple[float, float]]:
    t = geom.get("type")
    coords = geom.get("coordinates", [])
    if t == "Point":
        yield coords[0], coords[1]
    elif t == "MultiPoint":
        for c in coords:
            yield c[0], c[1]


def _iter_line_vertices(geom: dict) -> Iterable[tuple[float, float]]:
    t = geom.get("type")
    coords = geom.get("coordinates", [])
    if t == "LineString":
        for c in coords:
            yield c[0], c[1]
    elif t == "MultiLineString":
        for line in coords:
            for c in line:
                yield c[0], c[1]


def load_features(
    path: str | Path,
    *,
    keep: Callable[[dict], bool] | None = None,
) -> list[GeoFeature]:
    """Load Point / MultiPoint / LineString / MultiLineString features.

    `keep` may inspect each feature's properties dict and return False to drop.
    """
    data = json.loads(Path(path).read_text())
    out: list[GeoFeature] = []
    for feat in data.get("features", []):
        props = feat.get("properties") or {}
        if keep is not None and not keep(props):
            continue
        geom = feat.get("geometry") or {}
        gt = geom.get("type")
        if gt in {"Point", "MultiPoint"}:
            verts = list(_iter_points(geom))
            kind = "point"
        elif gt in {"LineString", "MultiLineString"}:
            verts = list(_iter_line_vertices(geom))
            kind = "line"
        else:
            continue
        if not verts:
            continue
        lats = [lat for _, lat in verts]
        lons = [lon for lon, _ in verts]
        out.append(GeoFeature(
            bbox=BBox(min(lats), min(lons), max(lats), max(lons)),
            kind=kind,
            vertices=verts,
        ))
    return out


def nearest_distance_m(
    lat: float, lon: float,
    features: list[GeoFeature],
    *,
    max_search_m: float,
    early_stop_m: float | None = None,
) -> float:
    """Minimum distance in meters from (lat, lon) to any feature.

    Returns +inf if no feature falls within `max_search_m`.
    """
    deg = max_search_m / 100_000.0
    best = math.inf
    for feat in features:
        if not feat.bbox.expand(deg).contains(lat, lon):
            continue
        if feat.kind == "point":
            for vlon, vlat in feat.vertices:
                d = haversine_m(lat, lon, vlat, vlon)
                if d < best:
                    best = d
                    if early_stop_m is not None and best <= early_stop_m:
                        return best
        else:
            verts = feat.vertices
            for i in range(len(verts) - 1):
                lon1, lat1 = verts[i]
                lon2, lat2 = verts[i + 1]
                d = point_segment_m(lat, lon, lat1, lon1, lat2, lon2)
                if d < best:
                    best = d
                    if early_stop_m is not None and best <= early_stop_m:
                        return best
    return best
