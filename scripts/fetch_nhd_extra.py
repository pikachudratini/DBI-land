"""Fetch NHD perennial flowlines + springs for the 4 newly-added states
and merge into the existing nhd_perennial_flowlines.geojson and
nhd_springs.geojson.

Reuses process_state() from fetch_nhd.py.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_nhd import OUT_DIR, SCRATCH, process_state  # noqa: E402

EXTRA_STATES = {
    "LA": "Louisiana",
    "FL": "Florida",
    "OR": "Oregon",
    "WA": "Washington",
}


def load_or_empty(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"type": "FeatureCollection", "features": []}


def append_unique(fc: dict, new_feats: list[dict], key: str) -> int:
    seen = {f["properties"].get(key) for f in fc["features"] if f["properties"].get(key)}
    added = 0
    for f in new_feats:
        k = f["properties"].get(key)
        if k and k in seen:
            continue
        fc["features"].append(f)
        if k:
            seen.add(k)
        added += 1
    return added


def main() -> None:
    flowlines = load_or_empty(OUT_DIR / "nhd_perennial_flowlines.geojson")
    springs = load_or_empty(OUT_DIR / "nhd_springs.geojson")
    print(f"existing: {len(flowlines['features'])} flowlines, "
          f"{len(springs['features'])} springs", flush=True)

    total_flow = 0
    total_spring = 0
    for code, name in EXTRA_STATES.items():
        flow, spring = process_state(code, name)
        total_flow += append_unique(flowlines, flow, "permanent_")
        total_spring += append_unique(springs, spring, "permanent_")

    (OUT_DIR / "nhd_perennial_flowlines.geojson").write_text(json.dumps(flowlines))
    (OUT_DIR / "nhd_springs.geojson").write_text(json.dumps(springs))
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print(f"wrote {len(flowlines['features'])} flowlines (+{total_flow}), "
          f"{len(springs['features'])} springs (+{total_spring})", flush=True)


if __name__ == "__main__":
    sys.exit(main())
