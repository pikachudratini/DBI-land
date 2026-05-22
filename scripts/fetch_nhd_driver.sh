#!/usr/bin/env bash
# Drive fetch_nhd.py one state per Python invocation so a single state's
# crash doesn't blow away progress, and so peak memory is bounded.
set -uo pipefail

STATES=(TX OK AR MO KS IA NE MN WI IL IN OH KY TN MS AL GA NC VA PA NY NJ MI SD ND)
PY=/root/DBI-land/.venv/bin/python

for code in "${STATES[@]}"; do
  for attempt in 1 2 3; do
    "$PY" -u /root/DBI-land/scripts/fetch_nhd.py one "$code"
    rc=$?
    if [ "$rc" -eq 0 ]; then
      break
    fi
    echo "[$code] attempt $attempt failed (exit $rc); retrying in 30s" >&2
    sleep 30
  done
done

"$PY" -u /root/DBI-land/scripts/fetch_nhd.py merge
