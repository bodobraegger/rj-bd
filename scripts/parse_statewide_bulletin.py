#!/usr/bin/env python3
"""
Extract beach statuses from INEA's statewide balneability bulletin.

Since late June 2026 this bulletin is the only current source for Rio
statuses, but its data pages are map images with green/red pins instead of
text. This script renders the relevant pages, detects the pins by color,
registers each map against the official monitoring point coordinates
(data/monitoringPoints.json) with an iterative-closest-point fit, and emits
point records in the same format as fetch_powerbi.py:

    [{"code", "beach", "city", "location", "status", "collectedAt", "lat", "lng"}, ...]

Points that cannot be matched confidently are omitted; the merge in
parse_inea_bulletin.py keeps their last known status. See
docs/inea-data-sources.md for the bulletin format.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import deque
from datetime import datetime
from pathlib import Path

from parse_inea_bulletin import MONTHS_PT

DEFAULT_POINTS_FILE = Path(__file__).parent.parent / 'data' / 'monitoringPoints.json'

RENDER_DPI = 150
# Map headings (full line, stripped) to point-set regions; None = not covered
HEADING_REGIONS = {
    'Zona Sudoeste': 'rio-oeste',
    'Zona Sul': 'rio-sul',
    'Niterói': 'niteroi',
    'Magé': None,
}
# Rio's per-zone split, same threshold as get_zone in parse_inea_bulletin
RIO_ZONE_LAT_SPLIT = -23.01

MIN_PIN_PIXELS, MAX_PIN_PIXELS = 60, 2000
MAX_PIN_SIZE = 60  # px, either dimension
MAP_GAP_PIXELS = 200  # vertical gap separating two maps on one page
LEGEND_WHITE_FRACTION = 0.6

ICP_ITERATIONS = 10
MAX_POINT_RESIDUAL = 50  # px: reject an individual point match beyond this
MIN_REGION_COVERAGE = 0.6  # reject a whole map if fewer points match

STATUS_BY_COLOR = {'green': 'proper', 'red': 'improper'}


def read_ppm(path):
    with open(path, 'rb') as file:
        data = file.read()
    header = []
    index = 0
    while len(header) < 4:
        while data[index] in b' \t\r\n':
            index += 1
        if data[index:index + 1] == b'#':
            while data[index] != 0x0A:
                index += 1
            continue
        start = index
        while data[index] not in b' \t\r\n':
            index += 1
        header.append(data[start:index])
    index += 1
    if header[0] != b'P6':
        raise ValueError(f'{path} is not a binary PPM')
    return int(header[1]), int(header[2]), data[index:]


def classify_pixel(r, g, b):
    # Pin green is dark and saturated; basemap greens are pale
    if g > 90 and g > r + 25 and g > b + 40 and r < 150:
        return 'green'
    # Pin red is strongly saturated; the basemap has no comparable reds
    if r > 150 and r > g + 70 and r > b + 60:
        return 'red'
    return None


def is_on_white_background(width, height, pixels, bbox):
    """Legend pins sit in a white legend box; map pins sit on basemap colors"""
    x_min, y_min, x_max, y_max = bbox
    margin = 8
    samples = 0
    white = 0
    for x in range(max(0, x_min - margin), min(width, x_max + margin + 1), 3):
        for y in (y_min - margin, y_max + margin):
            if 0 <= y < height:
                offset = (y * width + x) * 3
                samples += 1
                if min(pixels[offset:offset + 3]) > 235:
                    white += 1
    for y in range(max(0, y_min - margin), min(height, y_max + margin + 1), 3):
        for x in (x_min - margin, x_max + margin):
            if 0 <= x < width:
                offset = (y * width + x) * 3
                samples += 1
                if min(pixels[offset:offset + 3]) > 235:
                    white += 1
    return samples > 0 and white / samples > LEGEND_WHITE_FRACTION


def detect_pins(width, height, pixels):
    """Find pin blobs; anchor is the teardrop's bottom tip"""
    labels = {}
    for y in range(height):
        row = y * width * 3
        for x in range(width):
            offset = row + x * 3
            color = classify_pixel(pixels[offset], pixels[offset + 1], pixels[offset + 2])
            if color:
                labels[(x, y)] = color

    seen = set()
    pins = []
    for start, color in labels.items():
        if start in seen:
            continue
        queue = deque([start])
        seen.add(start)
        component = []
        while queue:
            x, y = queue.popleft()
            component.append((x, y))
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if labels.get(neighbor) == color and neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)

        if not MIN_PIN_PIXELS <= len(component) <= MAX_PIN_PIXELS:
            continue
        xs = [p[0] for p in component]
        ys = [p[1] for p in component]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        pin_width = bbox[2] - bbox[0] + 1
        pin_height = bbox[3] - bbox[1] + 1
        if pin_width > MAX_PIN_SIZE or pin_height > MAX_PIN_SIZE:
            continue
        if not 0.5 <= pin_width / pin_height <= 2.0:
            continue
        if is_on_white_background(width, height, pixels, bbox):
            continue
        pins.append({'color': color, 'x': (bbox[0] + bbox[2]) // 2, 'y': bbox[3]})
    return pins


def cluster_by_y(pins):
    """Split one page's pins into per-map clusters at large vertical gaps"""
    ordered = sorted(pins, key=lambda p: p['y'])
    clusters = []
    for pin in ordered:
        if clusters and pin['y'] - clusters[-1][-1]['y'] <= MAP_GAP_PIXELS:
            clusters[-1].append(pin)
        else:
            clusters.append([pin])
    return clusters


def one_to_one_matches(points, pins, project):
    """Greedy one-to-one assignment of points to pins by projected distance"""
    candidates = []
    for point in points:
        px, py = project(point['lng'], point['lat'])
        for pin in pins:
            distance = ((pin['x'] - px) ** 2 + (pin['y'] - py) ** 2) ** 0.5
            candidates.append((distance, id(point), id(pin), point, pin))
    candidates.sort(key=lambda c: c[0])
    used_points, used_pins = set(), set()
    matches = []
    for distance, point_id, pin_id, point, pin in candidates:
        if point_id in used_points or pin_id in used_pins:
            continue
        used_points.add(point_id)
        used_pins.add(pin_id)
        matches.append((point, pin, distance))
    return matches


def fit_projection(matches):
    """Per-axis linear least squares: pixel = scale * geo + offset"""
    n = len(matches)
    mean_lng = sum(p['lng'] for p, _, _ in matches) / n
    mean_lat = sum(p['lat'] for p, _, _ in matches) / n
    mean_x = sum(pin['x'] for _, pin, _ in matches) / n
    mean_y = sum(pin['y'] for _, pin, _ in matches) / n
    scale_x = (sum((p['lng'] - mean_lng) * (pin['x'] - mean_x) for p, pin, _ in matches)
               / (sum((p['lng'] - mean_lng) ** 2 for p, _, _ in matches) or 1e-12))
    scale_y = (sum((p['lat'] - mean_lat) * (pin['y'] - mean_y) for p, pin, _ in matches)
               / (sum((p['lat'] - mean_lat) ** 2 for p, _, _ in matches) or 1e-12))
    return lambda lng, lat: (scale_x * (lng - mean_lng) + mean_x,
                             scale_y * (lat - mean_lat) + mean_y)


def register_map(pins, points):
    """Match pins to known points via ICP; returns {code: (color, residual)}"""
    if len(pins) < 3 or len(points) < 3:
        return None

    lngs = [p['lng'] for p in points]
    lats = [p['lat'] for p in points]
    xs = [p['x'] for p in pins]
    ys = [p['y'] for p in pins]

    def bbox_project(lng, lat):
        x = (lng - min(lngs)) / ((max(lngs) - min(lngs)) or 1e-12) * (max(xs) - min(xs)) + min(xs)
        y = (max(lats) - lat) / ((max(lats) - min(lats)) or 1e-12) * (max(ys) - min(ys)) + min(ys)
        return x, y

    project = bbox_project
    matches = []
    for _ in range(ICP_ITERATIONS):
        matches = one_to_one_matches(points, pins, project)
        project = fit_projection(matches)

    matches = one_to_one_matches(points, pins, project)
    confident = [(point, pin, distance) for point, pin, distance in matches
                 if distance <= MAX_POINT_RESIDUAL]
    if len(confident) / len(points) < MIN_REGION_COVERAGE:
        return None
    return {point['code']: (pin['color'], distance) for point, pin, distance in confident}


def page_headings(pdf_path):
    """Yield (page_number, [headings]) for pages containing covered regions"""
    result = subprocess.run(['pdftotext', '-layout', pdf_path, '-'],
                            capture_output=True, text=True, check=True)
    for page_number, page_text in enumerate(result.stdout.split('\f'), start=1):
        headings = [line.strip() for line in page_text.splitlines()
                    if line.strip() in HEADING_REGIONS]
        if any(HEADING_REGIONS[h] for h in headings):
            yield page_number, headings


def render_page(pdf_path, page_number, directory):
    prefix = str(Path(directory) / f'page{page_number}')
    subprocess.run(['pdftoppm', '-r', str(RENDER_DPI), '-f', str(page_number),
                    '-l', str(page_number), pdf_path, prefix], check=True)
    rendered = list(Path(directory).glob(f'page{page_number}-*.ppm'))
    if len(rendered) != 1:
        raise FileNotFoundError(f'pdftoppm produced {len(rendered)} files for page {page_number}')
    return rendered[0]


def extract_bulletin_date(pdf_path, cover_text):
    filename_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', Path(pdf_path).name)
    if filename_match:
        day, month, year = (int(g) for g in filename_match.groups())
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            pass
    text_match = re.search(r'(\d{1,2})\s+([A-ZÇÃ]+)\s+(\d{4})', cover_text)
    if text_match:
        month = MONTHS_PT.get(text_match.group(2).lower())
        if month:
            try:
                return datetime(int(text_match.group(3)), month,
                                int(text_match.group(1))).date().isoformat()
            except ValueError:
                pass
    return None


def region_points(all_points, region):
    if region == 'rio-oeste':
        return [p for p in all_points
                if p['city'] == 'Rio de Janeiro' and p['lat'] <= RIO_ZONE_LAT_SPLIT]
    if region == 'rio-sul':
        return [p for p in all_points
                if p['city'] == 'Rio de Janeiro' and p['lat'] > RIO_ZONE_LAT_SPLIT]
    if region == 'niteroi':
        return [p for p in all_points if p['city'] == 'Niterói']
    raise ValueError(f'unknown region {region}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', help='statewide bulletin PDF')
    parser.add_argument('--points', default=str(DEFAULT_POINTS_FILE),
                        help='official monitoring point coordinates')
    parser.add_argument('--output', help='write JSON records here instead of stdout')
    args = parser.parse_args()

    with open(args.points, encoding='utf-8') as file:
        all_points = json.load(file)
    points_by_code = {p['code']: p for p in all_points}

    cover_text = subprocess.run(['pdftotext', '-layout', '-l', '1', args.pdf, '-'],
                                capture_output=True, text=True, check=True).stdout
    bulletin_date = extract_bulletin_date(args.pdf, cover_text)
    if not bulletin_date:
        print('✗ Could not determine bulletin date', file=sys.stderr)
        sys.exit(1)
    print(f'📅 Bulletin date: {bulletin_date}', file=sys.stderr)

    records = []
    with tempfile.TemporaryDirectory() as workdir:
        for page_number, headings in page_headings(args.pdf):
            ppm_path = render_page(args.pdf, page_number, workdir)
            width, height, pixels = read_ppm(ppm_path)
            clusters = cluster_by_y(detect_pins(width, height, pixels))
            if len(clusters) != len(headings):
                print(f'⚠️  Page {page_number}: {len(clusters)} pin clusters but '
                      f'{len(headings)} map headings {headings}; skipping page', file=sys.stderr)
                continue

            for heading, cluster in zip(headings, clusters):
                region = HEADING_REGIONS[heading]
                if not region:
                    continue
                expected = region_points(all_points, region)
                assignment = register_map(cluster, expected)
                if assignment is None:
                    print(f'⚠️  Page {page_number} "{heading}": registration failed '
                          f'({len(cluster)} pins vs {len(expected)} points); skipping map',
                          file=sys.stderr)
                    continue
                worst = max(distance for _, distance in assignment.values())
                print(f'✓ Page {page_number} "{heading}": {len(assignment)}/{len(expected)} '
                      f'points matched (worst residual {worst:.0f}px)', file=sys.stderr)
                for code, (color, _) in assignment.items():
                    point = points_by_code[code]
                    records.append({
                        'code': code,
                        'beach': point['beach'],
                        'city': point['city'],
                        'location': point['location'],
                        'status': STATUS_BY_COLOR[color],
                        'collectedAt': bulletin_date,
                        'lat': point['lat'],
                        'lng': point['lng'],
                    })

    if not records:
        print('✗ No statuses extracted from any map', file=sys.stderr)
        sys.exit(1)

    output = json.dumps(records, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as file:
            file.write(output + '\n')
    else:
        print(output)
    print(f'✓ Extracted {len(records)} point statuses from {args.pdf}', file=sys.stderr)


if __name__ == '__main__':
    main()
