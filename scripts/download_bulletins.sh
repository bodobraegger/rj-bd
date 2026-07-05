#!/bin/bash
# Download the most recent INEA bulletin PDFs for Rio de Janeiro and Niterói.
#
# Probes INEA's wp-content uploads going back day by day. INEA sometimes files
# a PDF under the following month's folder, so both are tried. A missing city
# is only a warning (the parser keeps its last known statuses); the script
# fails only when no bulletin is found at all.
#
# Note: INEA replaced the per-zone Rio bulletin with a statewide bulletin
# whose data pages are images (see docs/inea-data-sources.md), so the Rio
# download is expected to start failing once the last per-zone PDF ages out.
#
# Usage: download_bulletins.sh [output_dir]

set -u

OUTPUT_DIR="${1:-.}"
MAX_DAYS_BACK=14
BASE_URL="https://www.inea.rj.gov.br/wp-content/uploads"

RJ_NAMES=("Zona-sudoeste-e-Zona-sul" "Zona-oeste-e-Zona-sul")
NITEROI_NAMES=("Niter%C3%B3i" "Niteroi")

FOUND_RJ=""
FOUND_NITEROI=""

download_if_exists() {
    local url="$1" target="$2"
    if curl -f -s -I "$url" > /dev/null 2>&1; then
        if curl -f -s -L "$url" -o "$target"; then
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

[ -z "$FOUND_RJ" ] && echo "⚠️  No Rio de Janeiro bulletin found in the last $MAX_DAYS_BACK days"
[ -z "$FOUND_NITEROI" ] && echo "⚠️  No Niterói bulletin found in the last $MAX_DAYS_BACK days"

if [ -z "$FOUND_RJ" ] && [ -z "$FOUND_NITEROI" ]; then
    echo "✗ No bulletins found at all"
    exit 1
fi
