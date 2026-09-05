#!/bin/bash
# Download the most recent INEA bulletin PDFs.
#
# Per-city bulletins (Rio zone, Niterói): probes INEA's wp-content uploads
# going back day by day. INEA sometimes files a PDF under the following
# month's folder, so both are tried. The per-zone Rio bulletin is likely
# discontinued since late June 2026 (see docs/inea-data-sources.md).
#
# Statewide bulletin (image-based pin maps, parsed by
# parse_statewide_bulletin.py): link scraped from INEA's balneabilidade page,
# saved as statewide.pdf.
#
# A missing source is only a warning (the parser keeps its last known
# statuses); the script fails only when nothing is found at all.
#
# Usage: download_bulletins.sh [output_dir]

set -u

OUTPUT_DIR="${1:-.}"
mkdir -p "$OUTPUT_DIR"
MAX_DAYS_BACK=14
BASE_URL="https://www.inea.rj.gov.br/wp-content/uploads"

RJ_NAMES=("Zona-sudoeste-e-Zona-sul" "Zona-oeste-e-Zona-sul")
NITEROI_NAMES=("Niter%C3%B3i" "Niteroi")

FOUND_RJ=""
FOUND_NITEROI=""

# A browser User-Agent avoids WAFs that block the default curl UA outright,
# which is a more likely cause of total silence than an IP-range block: a
# residential curl with no UA override reaches every URL below in seconds.
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
CURL_PROBE=(--connect-timeout 10 --max-time 20 -A "$USER_AGENT")
CURL_FETCH=(--connect-timeout 10 --max-time 180 -A "$USER_AGENT")

download_if_exists() {
    local url="$1" target="$2"
    if curl -f -s "${CURL_PROBE[@]}" -I "$url" > /dev/null 2>&1; then
        if curl -f -s "${CURL_FETCH[@]}" -L "$url" -o "$target"; then
            echo "✓ Downloaded $target ($(stat -c%s "$target") bytes) from $url"
            return 0
        fi
    fi
    return 1
}

for days_ago in $(seq 0 $MAX_DAYS_BACK); do
    DATE_SUFFIX=$(date -d "$days_ago days ago" +%d-%m-%y)
    FOLDER=$(date -d "$days_ago days ago" +%Y/%m)
    FOLDER_NEXT_MONTH=$(date -d "$days_ago days ago + 1 month" +%Y/%m)

    if [ -z "$FOUND_RJ" ]; then
        for name in "${RJ_NAMES[@]}"; do
            for folder in "$FOLDER" "$FOLDER_NEXT_MONTH"; do
                if download_if_exists "$BASE_URL/$folder/$name-$DATE_SUFFIX.pdf" \
                                      "$OUTPUT_DIR/rj-bulletin-$DATE_SUFFIX.pdf"; then
                    FOUND_RJ="$OUTPUT_DIR/rj-bulletin-$DATE_SUFFIX.pdf"
                    break 2
                fi
            done
        done
    fi

    if [ -z "$FOUND_NITEROI" ]; then
        for name in "${NITEROI_NAMES[@]}"; do
            for folder in "$FOLDER" "$FOLDER_NEXT_MONTH"; do
                if download_if_exists "$BASE_URL/$folder/$name-$DATE_SUFFIX.pdf" \
                                      "$OUTPUT_DIR/niteroi-bulletin-$DATE_SUFFIX.pdf"; then
                    FOUND_NITEROI="$OUTPUT_DIR/niteroi-bulletin-$DATE_SUFFIX.pdf"
                    break 2
                fi
            done
        done
    fi

    if [ -n "$FOUND_RJ" ] && [ -n "$FOUND_NITEROI" ]; then
        break
    fi
done

FOUND_STATEWIDE=""
STATEWIDE_URL=$(curl -f -s "${CURL_PROBE[@]}" -L "https://www.inea.rj.gov.br/balneabilidade/" \
    | grep -oE 'href="[^"]*Boletim-de-Balneabilidade[^"]*\.pdf"' \
    | head -1 | sed 's/^href="//; s/"$//')
if [ -n "$STATEWIDE_URL" ]; then
    if curl -f -s "${CURL_FETCH[@]}" -L "$STATEWIDE_URL" -o "$OUTPUT_DIR/statewide.pdf"; then
        echo "✓ Downloaded $OUTPUT_DIR/statewide.pdf ($(stat -c%s "$OUTPUT_DIR/statewide.pdf") bytes) from $STATEWIDE_URL"
        FOUND_STATEWIDE="$OUTPUT_DIR/statewide.pdf"
    fi
fi

[ -z "$FOUND_RJ" ] && echo "⚠️  No Rio de Janeiro bulletin found in the last $MAX_DAYS_BACK days"
[ -z "$FOUND_NITEROI" ] && echo "⚠️  No Niterói bulletin found in the last $MAX_DAYS_BACK days"
[ -z "$FOUND_STATEWIDE" ] && echo "⚠️  No statewide bulletin link found on INEA's balneabilidade page"

if [ -z "$FOUND_RJ" ] && [ -z "$FOUND_NITEROI" ] && [ -z "$FOUND_STATEWIDE" ]; then
    echo "✗ No bulletins found at all"
    exit 1
fi
