"""Fetch OSM cell towers for the 4 newly-added states and merge into the
existing osm_towers.geojson.

Reuses helpers from fetch_osm_towers.py.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_osm_towers import fetch, OUT_PATH, PAUSE_S  # noqa: E402

EXTRA_ISO = ["US-LA", "US-FL", "US-OR", "US-WA"]


def main() -> None:
    if OUT_PATH.exists():
        existing = json.loads(OUT_PATH.read_text())
    else:
        existing = {"type": "FeatureCollection", "features": []}
    seen_ids = {f["properties"].get("osm_id") for f in existing["features"]}
    print(f"existing: {len(existing['features'])} towers", flush=True)

    added = 0
    for i, iso in enumerate(EXTRA_ISO):
        print(f"[{iso}] querying ({i+1}/{len(EXTRA_ISO)})", flush=True)
        feats = fetch(iso)
        new_feats = [f for f in feats if f["properties"].get("osm_id") not in seen_ids]
        existing["features"].extend(new_feats)
        for f in new_feats:
            seen_ids.add(f["properties"].get("osm_id"))
        added += len(new_feats)
        print(f"[{iso}] +{len(new_feats)} new towers", flush=True)
        if i < len(EXTRA_ISO) - 1:
            time.sleep(PAUSE_S)

    OUT_PATH.write_text(json.dumps(existing))
    print(f"wrote {len(existing['features'])} total towers (+{added}) -> {OUT_PATH}",
          flush=True)


if __name__ == "__main__":
    sys.exit(main())
