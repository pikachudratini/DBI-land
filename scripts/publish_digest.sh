#!/usr/bin/env bash
# Publish the latest passing-digest HTML to the gh-pages branch so it's
# viewable at https://pikachudratini.github.io/DBI-land/.
#
# Usage:
#   scripts/publish_digest.sh                # publishes newest artifacts/digest-passing_v*.html
#   scripts/publish_digest.sh path/to/x.html # publishes a specific file
#
# Idempotent: if the chosen file is already on gh-pages with the same bytes,
# does nothing.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ART_DIR="$REPO_DIR/artifacts"
WORKTREE="${TMPDIR:-/tmp}/dbi-pages-$$"

if [ "$#" -ge 1 ]; then
    SRC="$1"
else
    SRC="$(ls -1t "$ART_DIR"/digest-passing_v*.html 2>/dev/null | head -1 || true)"
fi
if [ -z "${SRC:-}" ] || [ ! -f "$SRC" ]; then
    echo "publish_digest: no digest HTML found (looked in $ART_DIR/digest-passing_v*.html)" >&2
    exit 1
fi
BASENAME="$(basename "$SRC")"
echo "publish_digest: source = $SRC"

cleanup() {
    git -C "$REPO_DIR" worktree remove --force "$WORKTREE" 2>/dev/null || true
}
trap cleanup EXIT

git -C "$REPO_DIR" fetch origin gh-pages --quiet
git -C "$REPO_DIR" worktree add "$WORKTREE" origin/gh-pages --quiet
cd "$WORKTREE"
git checkout -B gh-pages --quiet

cp "$SRC" "$WORKTREE/$BASENAME"
cp "$SRC" "$WORKTREE/index.html"

git add "$BASENAME" index.html
if git diff --cached --quiet; then
    echo "publish_digest: nothing changed; gh-pages already serves $BASENAME"
    exit 0
fi

git -c user.email=andrewailist@gmail.com -c user.name=pikachudratini \
    commit -m "Publish $BASENAME" --quiet
git push origin gh-pages --quiet

echo "publish_digest: pushed."
echo "  homepage:  https://pikachudratini.github.io/DBI-land/"
echo "  permalink: https://pikachudratini.github.io/DBI-land/$BASENAME"
echo "  (Pages build takes ~30-90s the first time after a push.)"
