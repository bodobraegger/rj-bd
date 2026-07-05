#!/usr/bin/env python3
"""
Regenerate data/monitoringPoints.json from fetch_powerbi.py output.

The file holds INEA's official coordinates for every monitoring point on a
covered beach. It changes only when INEA adds or moves points, so it is
committed rather than fetched at runtime: parse_statewide_bulletin.py needs
these coordinates even when the Power BI API is unreachable.

Usage: fetch_powerbi.py --output powerbi.json && generate_monitoring_points.py powerbi.json
"""
import json
import sys
from pathlib import Path

from parse_inea_bulletin import get_beach_from_point_code

OUTPUT_FILE = Path(__file__).parent.parent / 'data' / 'monitoringPoints.json'


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    with open(sys.argv[1], encoding='utf-8') as file:
        records = json.load(file)

    points = []
    for record in records:
        beach = get_beach_from_point_code(record['code'])
        if not beach:
            continue
        points.append({
            'code': record['code'],
            'beach': beach,
            'city': record['city'],
            'location': record['location'],
            'lat': record['lat'],
            'lng': record['lng'],
        })

    points.sort(key=lambda p: (p['city'], p['beach'], p['code']))
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as file:
        json.dump(points, file, ensure_ascii=False, indent=2)
        file.write('\n')
    print(f'✓ Wrote {len(points)} monitoring points to {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
