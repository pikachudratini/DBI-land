"""Pull cell towers / masts / communication antennae from OpenStreetMap
via the Overpass API, one state at a time.

FCC ASR is unreachable from this sandbox (broken redirect on www.fcc.gov);
OSM is a free substitute with lower but useful coverage.

Output: data/gis/osm_towers.geojson  (Point FeatureCollection)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

STATES_ISO = [
    "US-TX", "US-OK", "US-AR", "US-MO", "US-KS", "US-IA", "US-NE", "US-MN",
    "US-WI", "US-IL", "US-IN", "US-OH", "US-KY", "US-TN", "US-MS", "US-AL",
    "US-GA", "US-NC", "US-VA", "US-PA", "US-NY", "US-NJ", "US-MI", "US-SD",
    "US-ND",
]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUT_PATH = Path("data/gis/osm_towers.geojson")
PAUSE_S = 30.0  # be polite to overpass-api.de


def query_for(iso: str) -> str:
    return (
        f"[out:json][timeout:180];\n"
        f'area["ISO3166-2"="{iso}"][admin_level=4]->.a;\n'
        f"(\n"
        f'  node["man_made"="communications_tower"](area.a);\n'
        f'  node["man_made"="mast"](area.a);\n'
        f'  node["tower:type"="communication"](area.a);\n'
        f");\n"
        f"out body;\n"
    )


def fetch(iso: str) -> list[dict]:
    body = query_for(iso).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=body,
        headers={"Content-Type": "text/plain", "User-Agent": "DBI-land bot"},
        method="POST",
    )
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read().decode("utf-8"))
            elements = data.get("elements", [])
            return [
                {
                    "type": "Feature",
                    "properties": {
                        "osm_id": e["id"],
                        "iso": iso,
                        **{k: v for k, v in (e.get("tags") or {}).items()},
                    },
                    "geometry": {"type": "Point", "coordinates": [e["lon"], e["lat"]]},
                }
                for e in elements
                if "lat" in e and "lon" in e
            ]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            print(f"[{iso}] attempt {attempt+1} failed: {e}; backing off", flush=True)
            time.sleep(60 * (attempt + 1))
    print(f"[{iso}] giving up: {last_err}", flush=True)
    return []


def main() -> None:
    all_features: list[dict] = []
    for i, iso in enumerate(STATES_ISO):
        print(f"[{iso}] querying ({i+1}/{len(STATES_ISO)})", flush=True)
        feats = fetch(iso)
        print(f"[{iso}] +{len(feats)} towers", flush=True)
        all_features.extend(feats)
        if i < len(STATES_ISO) - 1:
            time.sleep(PAUSE_S)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": all_features}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(fc, f)
    print(f"wrote {len(all_features)} towers -> {OUT_PATH}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
