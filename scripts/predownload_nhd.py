"""Pre-fetch all NHD state zips in parallel so the sequential processing
driver doesn't wait on downloads. Skips states that already have a per-state
cache or a complete zip on disk.

Atomic: writes to .download then renames to the final .zip name — so the
processing driver's existence check never sees a half-downloaded file.
"""
from __future__ import annotations

import concurrent.futures
import shutil
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_nhd import OUT_DIR, SCRATCH, STATES, state_url  # noqa: E402


def per_state_cached(code: str) -> bool:
    return (OUT_DIR / "_per_state" / f"{code}_flowlines.geojson").exists()


def predownload(code: str, name: str) -> str:
    dest = SCRATCH / f"NHD_{code}.zip"
    if per_state_cached(code):
        return f"[{code}] skip (already in per-state cache)"
    if dest.exists() and dest.stat().st_size > 0:
        return f"[{code}] skip (zip already on disk, {dest.stat().st_size // 1_000_000} MB)"
    SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".download")
    try:
        with urllib.request.urlopen(state_url(name), timeout=600) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, length=1 << 20)
        tmp.rename(dest)
        return f"[{code}] downloaded {dest.stat().st_size // 1_000_000} MB"
    except Exception as e:
        tmp.unlink(missing_ok=True)
        return f"[{code}] FAILED: {e}"


def main() -> None:
    todo = [(code, name) for code, name in STATES.items() if not per_state_cached(code)]
    print(f"predownload: {len(todo)}/{len(STATES)} states need fetching", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for msg in ex.map(lambda kv: predownload(*kv), todo):
            print(msg, flush=True)


if __name__ == "__main__":
    sys.exit(main())
