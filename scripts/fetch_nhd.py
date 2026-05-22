"""Download per-state NHD shapefiles and emit two filtered GeoJSONs.

For each state:
  1. download the Shape zip from USGS S3
  2. extract only NHDFlowline + NHDPoint shapefiles
  3. filter to FCode 46006 (perennial stream) and 45800 (spring/seep)
  4. emit features into combined output GeoJSONs

Outputs:
  data/gis/nhd_perennial_flowlines.geojson
  data/gis/nhd_springs.geojson
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

import shapefile

STATES = {
    "TX": "Texas", "OK": "Oklahoma", "AR": "Arkansas", "MO": "Missouri",
    "KS": "Kansas", "IA": "Iowa", "NE": "Nebraska", "MN": "Minnesota",
    "WI": "Wisconsin", "IL": "Illinois", "IN": "Indiana", "OH": "Ohio",
    "KY": "Kentucky", "TN": "Tennessee", "MS": "Mississippi", "AL": "Alabama",
    "GA": "Georgia", "NC": "North_Carolina", "VA": "Virginia", "PA": "Pennsylvania",
    "NY": "New_York", "NJ": "New_Jersey", "MI": "Michigan", "SD": "South_Dakota",
    "ND": "North_Dakota",
}

BASE = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/State/Shape"
SCRATCH = Path("data/gis/_nhd_scratch")
OUT_DIR = Path("data/gis")
PERENNIAL_FCODE = 46006
SPRING_FCODE = 45800


def state_url(name: str) -> str:
    return f"{BASE}/NHD_H_{name}_State_Shape.zip"


def download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached: {dest.name} ({dest.stat().st_size // 1_000_000} MB)", flush=True)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=600) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    tmp.rename(dest)


def extract_targets(zip_path: Path, out_dir: Path) -> dict[str, list[Path]]:
    """Extract NHDFlowline* + NHDPoint* shapefile components.

    Large states split a layer across multiple files (NHDFlowline_0.shp,
    NHDFlowline_1.shp, ...) to stay under the 2 GB shapefile limit, so we
    accept any stem starting with the target prefix.
    """
    prefixes = ("NHDFlowline", "NHDPoint")
    found: dict[str, list[Path]] = {p: [] for p in prefixes}
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = Path(info.filename).name
            stem = Path(name).stem
            ext = Path(name).suffix.lower()
            if ext not in (".shp", ".shx", ".dbf", ".prj"):
                continue
            for prefix in prefixes:
                # Exact match or split form (NHDFlowline, NHDFlowline_0, ...).
                # Reject NHDFlowlineVAA / NHDPointEventFC / etc.
                if stem == prefix or (
                    stem.startswith(prefix + "_") and stem[len(prefix) + 1:].isdigit()
                ):
                    out_path = out_dir / name
                    with z.open(info) as src, open(out_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    if ext == ".shp":
                        found[prefix].append(out_path)
                    break
    return found


def features_from_shp(shp_path: Path, fcode: int) -> list[dict]:
    """Read shapefile, filter by FCODE, return GeoJSON features in WGS84.

    NHD .dbf files contain non-ASCII gnis_name values (e.g., Bayou names with
    é, ñ), so utf-8 decoding fails on some states — latin-1 is lossless for
    1-byte legacy encodings.
    """
    feats: list[dict] = []
    with shapefile.Reader(str(shp_path.with_suffix("")), encoding="latin-1") as r:
        field_names = [f[0] for f in r.fields[1:]]
        fc_idx = next(
            (i for i, n in enumerate(field_names) if n.lower() == "fcode"), -1
        )
        if fc_idx < 0:
            return []
        for sr in r.iterShapeRecords():
            rec = sr.record
            try:
                if int(rec[fc_idx]) != fcode:
                    continue
            except (TypeError, ValueError):
                continue
            geom = sr.shape.__geo_interface__
            props = {field_names[i]: rec[i] for i in range(len(field_names))}
            feats.append({"type": "Feature", "properties": props, "geometry": geom})
    return feats


def process_state(state_code: str, state_name: str) -> tuple[list[dict], list[dict]]:
    """Returns (perennial_flowlines, springs) features for one state."""
    print(f"[{state_code}] starting", flush=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    zip_path = SCRATCH / f"NHD_{state_code}.zip"
    work_dir = SCRATCH / state_code
    try:
        download(state_url(state_name), zip_path)
        size_mb = zip_path.stat().st_size // 1_000_000
        print(f"[{state_code}] downloaded {size_mb} MB", flush=True)
        targets = extract_targets(zip_path, work_dir)
        flowlines: list[dict] = []
        springs: list[dict] = []
        for shp in targets.get("NHDFlowline", []):
            flowlines.extend(features_from_shp(shp, PERENNIAL_FCODE))
        for shp in targets.get("NHDPoint", []):
            springs.extend(features_from_shp(shp, SPRING_FCODE))
        print(f"[{state_code}] kept {len(flowlines)} flowlines, {len(springs)} springs",
              flush=True)
        return flowlines, springs
    except Exception as e:
        print(f"[{state_code}] FAILED: {e}", flush=True)
        return [], []
    finally:
        # Free disk: drop the zip and extracted shapefiles once filtered
        if zip_path.exists():
            zip_path.unlink()
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)


def write_geojson(features: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": features}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, default=str)
    print(f"wrote {len(features)} features -> {out_path}", flush=True)


def per_state_paths(code: str) -> tuple[Path, Path]:
    cache = OUT_DIR / "_per_state"
    return cache / f"{code}_flowlines.geojson", cache / f"{code}_springs.geojson"


def run_one(code: str) -> None:
    """Process a single state and write its per-state cache. Called from
    a bash driver so each state is its own short-lived process."""
    name = STATES[code]
    cache = OUT_DIR / "_per_state"
    cache.mkdir(parents=True, exist_ok=True)
    f_path, s_path = per_state_paths(code)
    if f_path.exists() and s_path.exists():
        print(f"[{code}] cached, skipping", flush=True)
        return
    flow, spring = process_state(code, name)
    f_path.write_text(json.dumps({"type": "FeatureCollection", "features": flow}, default=str))
    s_path.write_text(json.dumps({"type": "FeatureCollection", "features": spring}, default=str))
    print(f"[{code}] wrote per-state cache "
          f"({len(flow)} flowlines, {len(spring)} springs)", flush=True)


def merge_outputs() -> None:
    """Concatenate every per-state cache into the two final GeoJSONs."""
    for layer, suffix in (("flowlines", "_flowlines.geojson"),
                          ("springs", "_springs.geojson")):
        out_path = OUT_DIR / f"nhd_{'perennial_' if layer == 'flowlines' else ''}{layer}.geojson"
        total = 0
        with open(out_path, "w", encoding="utf-8") as out:
            out.write('{"type":"FeatureCollection","features":[')
            first = True
            for code in STATES:
                cache_path = OUT_DIR / "_per_state" / f"{code}{suffix}"
                if not cache_path.exists():
                    continue
                feats = json.loads(cache_path.read_text())["features"]
                for f in feats:
                    if not first:
                        out.write(",")
                    json.dump(f, out, default=str)
                    first = False
                    total += 1
            out.write("]}")
        print(f"wrote {total} {layer} -> {out_path}", flush=True)


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "merge":
        merge_outputs()
        shutil.rmtree(SCRATCH, ignore_errors=True)
        return
    if len(sys.argv) >= 3 and sys.argv[1] == "one":
        run_one(sys.argv[2])
        return
    # Default: in-process all states (legacy path).
    for code in STATES:
        run_one(code)
    merge_outputs()
    shutil.rmtree(SCRATCH, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
