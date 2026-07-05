#!/bin/bash
# Local smoke test: download current bulletins, fetch Power BI data, run the
# full generation pipeline into a temp directory, and validate the output.
# Does not touch data/beachData.json.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

echo "🔍 INEA pipeline smoke test (work dir: $WORK_DIR)"
echo "=============================================="

echo ""
echo "📥 Downloading bulletins..."
"$SCRIPT_DIR/download_bulletins.sh" "$WORK_DIR" || true

echo ""
echo "⚡ Fetching Power BI data..."
if ! python3 "$SCRIPT_DIR/fetch_powerbi.py" --output "$WORK_DIR/powerbi.json"; then
    echo "⚠️  Power BI fetch failed; continuing with PDFs only"
    rm -f "$WORK_DIR/powerbi.json"
fi

echo ""
echo "🐍 Generating beach data..."
POWERBI_ARGS=()
[ -f "$WORK_DIR/powerbi.json" ] && POWERBI_ARGS=(--powerbi-file "$WORK_DIR/powerbi.json")
python3 "$SCRIPT_DIR/parse_inea_bulletin.py" "$WORK_DIR"/*bulletin*.pdf \
    "${POWERBI_ARGS[@]}" \
    --baseline "$REPO_DIR/data/beachData.json" \
    --output "$WORK_DIR/beachData.json"

echo ""
echo "🧪 Validating generated data..."
python3 "$SCRIPT_DIR/test_parsing.py" "$WORK_DIR/beachData.json"

echo ""
echo "✓ Smoke test completed successfully"
