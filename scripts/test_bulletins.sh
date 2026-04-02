#!/bin/bash
# Test script to download and parse INEA bulletins

set -e  # Exit on error

echo "🔍 Testing INEA Bulletin Download and Parsing"
echo "=============================================="

# Clean up old test files
rm -f *-bulletin-*.pdf test-beach-data.json

SUCCESS_RJ=0
SUCCESS_NITEROI=0

# Try to find bulletins from the last 14 days
for days_ago in {0..14}; do
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        YEAR=$(date -v-${days_ago}d +%Y)
        MONTH=$(date -v-${days_ago}d +%m)
        DATE_OLD=$(date -v-${days_ago}d +%d-%m-%y)
        DATE_DISPLAY=$(date -v-${days_ago}d +"%Y-%m-%d")
    else
        # Linux
        YEAR=$(date -d "$days_ago days ago" +%Y)
        MONTH=$(date -d "$days_ago days ago" +%m)
        DATE_OLD=$(date -d "$days_ago days ago" +%d-%m-%y)
        DATE_DISPLAY=$(date -d "$days_ago days ago" +"%Y-%m-%d")
    fi
    
    echo ""
    echo "📅 Checking $DATE_DISPLAY ($days_ago days ago)..."
    
    # Try Rio de Janeiro bulletin (new format names)
    if [ $SUCCESS_RJ -eq 0 ]; then
        # Try both current month and next month folders (INEA sometimes uploads to wrong month)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            MONTH_NEXT=$(date -v-${days_ago}d -v+1m +%m)
            YEAR_NEXT=$(date -v-${days_ago}d -v+1m +%Y)
        else
            MONTH_NEXT=$(date -d "$days_ago days ago + 1 month" +%m)
            YEAR_NEXT=$(date -d "$days_ago days ago + 1 month" +%Y)
        fi
        
        for RJ_NAME in "Zona-sudoeste-e-Zona-sul" "Zona-oeste-e-Zona-sul"; do
            FILENAME_RJ="${RJ_NAME}-${DATE_OLD}.pdf"
            
            # Try current month folder
            URL_RJ="https://www.inea.rj.gov.br/wp-content/uploads/${YEAR}/${MONTH}/${FILENAME_RJ}"
            echo "  🔍 Trying RJ: $URL_RJ"
            
            if curl -f -s -I "$URL_RJ" > /dev/null 2>&1; then
                echo "  ✓ Found Rio bulletin!"
                curl -f -L "$URL_RJ" -o "rj-bulletin-${DATE_OLD}.pdf"
                SIZE=$(stat -c%s "rj-bulletin-${DATE_OLD}.pdf" 2>/dev/null || stat -f%z "rj-bulletin-${DATE_OLD}.pdf")
                echo "  ✓ Downloaded: rj-bulletin-${DATE_OLD}.pdf ($SIZE bytes)"
                SUCCESS_RJ=1
                break
            fi
            
            # Try next month folder
            URL_RJ_NEXT="https://www.inea.rj.gov.br/wp-content/uploads/${YEAR_NEXT}/${MONTH_NEXT}/${FILENAME_RJ}"
            echo "  🔍 Trying RJ (next month): $URL_RJ_NEXT"
            
            if curl -f -s -I "$URL_RJ_NEXT" > /dev/null 2>&1; then
                echo "  ✓ Found Rio bulletin in next month folder!"
                curl -f -L "$URL_RJ_NEXT" -o "rj-bulletin-${DATE_OLD}.pdf"
                SIZE=$(stat -c%s "rj-bulletin-${DATE_OLD}.pdf" 2>/dev/null || stat -f%z "rj-bulletin-${DATE_OLD}.pdf")
                echo "  ✓ Downloaded: rj-bulletin-${DATE_OLD}.pdf ($SIZE bytes)"
                SUCCESS_RJ=1
                break
            fi
        done
    fi
    
    # Try Niterói bulletin
    if [ $SUCCESS_NITEROI -eq 0 ]; then
        # Try both current month and next month folders
        if [[ "$OSTYPE" == "darwin"* ]]; then
            MONTH_NEXT=$(date -v-${days_ago}d -v+1m +%m)
            YEAR_NEXT=$(date -v-${days_ago}d -v+1m +%Y)
        else
            MONTH_NEXT=$(date -d "$days_ago days ago + 1 month" +%m)
            YEAR_NEXT=$(date -d "$days_ago days ago + 1 month" +%Y)
        fi
        
        for NITEROI_NAME in "Niterói" "Niteroi"; do
            FILENAME_NITEROI="${NITEROI_NAME}-${DATE_OLD}.pdf"
            # URL encode the filename (ó = %C3%B3)
            FILENAME_NITEROI_ENCODED=$(echo "$FILENAME_NITEROI" | sed 's/ó/%C3%B3/g')
            
            # Try current month folder
            URL_NITEROI="https://www.inea.rj.gov.br/wp-content/uploads/${YEAR}/${MONTH}/${FILENAME_NITEROI_ENCODED}"
            echo "  🔍 Trying Niterói: $URL_NITEROI"
            
            if curl -f -s -I "$URL_NITEROI" > /dev/null 2>&1; then
                echo "  ✓ Found Niterói bulletin!"
                curl -f -L "$URL_NITEROI" -o "niteroi-bulletin-${DATE_OLD}.pdf"
                SIZE=$(stat -c%s "niteroi-bulletin-${DATE_OLD}.pdf" 2>/dev/null || stat -f%z "niteroi-bulletin-${DATE_OLD}.pdf")
                echo "  ✓ Downloaded: niteroi-bulletin-${DATE_OLD}.pdf ($SIZE bytes)"
                SUCCESS_NITEROI=1
                break
            fi
            
            # Try next month folder
            URL_NITEROI_NEXT="https://www.inea.rj.gov.br/wp-content/uploads/${YEAR_NEXT}/${MONTH_NEXT}/${FILENAME_NITEROI_ENCODED}"
            echo "  🔍 Trying Niterói (next month): $URL_NITEROI_NEXT"
            
            if curl -f -s -I "$URL_NITEROI_NEXT" > /dev/null 2>&1; then
                echo "  ✓ Found Niterói bulletin in next month folder!"
                curl -f -L "$URL_NITEROI_NEXT" -o "niteroi-bulletin-${DATE_OLD}.pdf"
                SIZE=$(stat -c%s "niteroi-bulletin-${DATE_OLD}.pdf" 2>/dev/null || stat -f%z "niteroi-bulletin-${DATE_OLD}.pdf")
                echo "  ✓ Downloaded: niteroi-bulletin-${DATE_OLD}.pdf ($SIZE bytes)"
                SUCCESS_NITEROI=1
                break
            fi
        done
    fi
    
    # Exit loop if both found
    if [ $SUCCESS_RJ -eq 1 ] && [ $SUCCESS_NITEROI -eq 1 ]; then
        echo ""
        echo "✓ Found both bulletins!"
        break
    fi
done

echo ""
echo "=============================================="
echo "📊 Download Summary:"
echo "=============================================="

# Check results
if [ $SUCCESS_RJ -eq 0 ] && [ $SUCCESS_NITEROI -eq 0 ]; then
    echo "✗ Could not find any bulletins in the last 14 days"
    exit 1
fi

if [ $SUCCESS_RJ -eq 1 ]; then
    echo "✓ Rio de Janeiro bulletin: Downloaded"
else
    echo "⚠️  Rio de Janeiro bulletin: Not found"
fi

if [ $SUCCESS_NITEROI -eq 1 ]; then
    echo "✓ Niterói bulletin: Downloaded"
else
    echo "⚠️  Niterói bulletin: Not found"
fi

# Test parsing with pdftotext
echo ""
echo "=============================================="
echo "📄 Testing PDF Text Extraction:"
echo "=============================================="

# Check if pdftotext is installed
if ! command -v pdftotext &> /dev/null; then
    echo "⚠️  pdftotext not found. Install with:"
    echo "   Ubuntu/Debian: sudo apt-get install poppler-utils"
    echo "   macOS: brew install poppler"
    echo ""
    echo "Skipping text extraction test..."
else
    for pdf in *-bulletin-*.pdf; do
        if [ -f "$pdf" ]; then
            echo ""
            echo "📄 Extracting text from $pdf..."
            TEXT=$(pdftotext -layout "$pdf" - 2>/dev/null)
            
            if [ $? -eq 0 ]; then
                echo "✓ Text extraction successful"
                
                # Check for key markers
                if echo "$TEXT" | grep -qi "BOLETIM"; then
                    echo "  ✓ Found 'BOLETIM' in text"
                fi
                
                if echo "$TEXT" | grep -qi "PRÓPRIA\|PROPRIA"; then
                    PROPRIA_COUNT=$(echo "$TEXT" | grep -oi "PRÓPRIA\|PROPRIA" | wc -l)
                    echo "  ✓ Found 'Própria' status ($PROPRIA_COUNT times)"
                fi
                
                if echo "$TEXT" | grep -qi "IMPRÓPRIA\|IMPROPRIA"; then
                    IMPROPRIA_COUNT=$(echo "$TEXT" | grep -oi "IMPRÓPRIA\|IMPROPRIA" | wc -l)
                    echo "  ✓ Found 'Imprópria' status ($IMPROPRIA_COUNT times)"
                fi
                
                # Show first few lines
                echo ""
                echo "  First few lines of extracted text:"
                echo "$TEXT" | head -5 | sed 's/^/    /'
            else
                echo "✗ Text extraction failed"
            fi
        fi
    done
fi

# Test Python parsing
echo ""
echo "=============================================="
echo "🐍 Testing Python Parsing Script:"
echo "=============================================="
echo ""

if python3 scripts/parse_inea_bulletin.py; then
    echo ""
    echo "✓ Parsing successful!"
    
    # Show generated JSON summary
    if [ -f "data/beachData.json" ]; then
        echo ""
        echo "📋 Generated JSON Summary:"
        echo "=============================================="
        
        # Use Python to pretty-print summary
        python3 -c "
import json
with open('data/beachData.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    
print(f\"Last Update: {data['lastUpdate']}\")
print(f\"Total Beaches: {len(data['beaches'])}\")
print()

# Count by city
rj = [b for b in data['beaches'] if b.get('city') == 'Rio de Janeiro']
niteroi = [b for b in data['beaches'] if b.get('city') == 'Niterói']
print(f\"Rio de Janeiro: {len(rj)} beaches\")
print(f\"Niterói: {len(niteroi)} beaches\")
print()

# Count by status
proper = [b for b in data['beaches'] if b['status'] == 'proper']
improper = [b for b in data['beaches'] if b['status'] == 'improper']
unknown = [b for b in data['beaches'] if b['status'] == 'unknown']

print(f\"Status breakdown:\")
print(f\"  ✓ Proper: {len(proper)}\")
print(f\"  ✗ Improper: {len(improper)}\")
print(f\"  ? Unknown: {len(unknown)}\")
print()

# Show a few examples
if improper:
    print('Improper beaches:')
    for b in improper[:5]:
        print(f\"  - {b['name']} ({b.get('city', 'Unknown')})\")
    if len(improper) > 5:
        print(f\"  ... and {len(improper) - 5} more\")
"
    fi
else
    echo ""
    echo "✗ Parsing failed!"
    exit 1
fi

echo ""
echo "=============================================="
echo "✓ All tests completed successfully!"
echo "=============================================="
