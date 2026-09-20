#!/bin/bash
# Refresh data/beachData.json from every INEA source, validate, and commit.
#
# Shared by the GitHub Actions workflow and the local systemd timer
# (scripts/systemd/). INEA drops connections from outside Brazil, so the
# bulletin PDFs only download when this runs on a Brazilian IP; Power BI
# is reachable from anywhere. See docs/inea-data-sources.md.
#
# Usage: update_data.sh [--push]
#   --push  commit data/beachData.json when it changed and push to origin

set -euo pipefail
cd "$(dirname "$0")/.."

PUSH=""
[ "${1:-}" = "--push" ] && PUSH=1

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

./scripts/download_bulletins.sh "$WORK_DIR" \
    || echo "⚠️  Bulletin download failed; relying on Power BI and baseline"

python3 scripts/fetch_powerbi.py --output "$WORK_DIR/powerbi.json" \
    || rm -f "$WORK_DIR/powerbi.json"

POINT_ARGS=()
[ -f "$WORK_DIR/powerbi.json" ] && POINT_ARGS+=(--points-file "$WORK_DIR/powerbi.json")

if [ -f "$WORK_DIR/statewide.pdf" ]; then
    if python3 scripts/parse_statewide_bulletin.py "$WORK_DIR/statewide.pdf" \
            --output "$WORK_DIR/statewide_points.json"; then
        POINT_ARGS+=(--points-file "$WORK_DIR/statewide_points.json")
    fi
fi

shopt -s nullglob
BULLETINS=("$WORK_DIR"/*bulletin*.pdf)
shopt -u nullglob

python3 scripts/parse_inea_bulletin.py "${BULLETINS[@]}" "${POINT_ARGS[@]}"
python3 scripts/test_parsing.py

if git diff --quiet data/beachData.json; then
    echo "No data changes to commit"
    exit 0
fi
[ -n "$PUSH" ] || exit 0

git add data/beachData.json
git commit -m "chore(data): update beach data"
git push
