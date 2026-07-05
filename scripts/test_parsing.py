#!/usr/bin/env python3
"""
Validate generated beach data against the parser's own mappings.

Expectations are derived from parse_inea_bulletin.py (beach lists, point-code
mappings) so they cannot drift from the code. Structural problems fail the
suite (non-zero exit); data-quality observations only warn.

Usage: test_parsing.py [path/to/beachData.json]
"""
import json
import sys
from pathlib import Path

from parse_inea_bulletin import (
    BEACH_COORDS,
    NITEROI_BEACHES,
    RJ_BEACHES,
    SPECIFIC_POINT_MAPPINGS,
    get_beach_from_point_code,
    normalize_point_code,
)

DEFAULT_DATA_FILE = Path(__file__).parent.parent / 'data' / 'beachData.json'
VALID_STATUSES = {'proper', 'improper', 'attention', 'unknown'}
# Generous bounding box around Rio de Janeiro and Niterói
LAT_BOUNDS = (-23.2, -22.7)
LNG_BOUNDS = (-43.8, -42.9)


def test_point_code_normalization(data):
    """Point codes normalize consistently across padding schemes"""
    cases = [
        ('BD03', 'BD3'), ('BD003', 'BD3'), ('BD011', 'BD11'),
        ('FL008', 'FL8'), ('AR00', 'AR0'), ('AR000', 'AR0'),
        ('CP100', 'CP100'),
    ]
    failures = [(raw, expected, normalize_point_code(raw))
                for raw, expected in cases if normalize_point_code(raw) != expected]
    for raw, expected, actual in failures:
        print(f"❌ FAIL: normalize_point_code('{raw}') = '{actual}', expected '{expected}'")
    if not failures:
        print("✅ PASS: Point code normalization")
    return not failures


def test_edge_case_mappings(data):
    """Edge-case point codes map to the right beaches in both padding schemes"""
    cases = {
        'FL000': 'Flamengo', 'FL004': 'Flamengo', 'FL008': 'Glória',
        'BD05': 'Barra da Tijuca', 'BD007': 'Barra da Tijuca', 'BD09': 'Barra da Tijuca',
        'BD10': 'Barra da Tijuca II',
        'BD00': 'Recreio', 'BD002': 'Recreio',
        'BD03': 'Recreio/Reserva', 'BD011': 'Recreio/Reserva',
        'AD000': 'Adão', 'IC001': 'Icaraí',
    }
    failures = []
    for code, expected in cases.items():
        actual = get_beach_from_point_code(code)
        if actual != expected:
            failures.append(f"{code} -> {actual}, expected {expected}")
    for failure in failures:
        print(f"❌ FAIL: {failure}")
    if not failures:
        print(f"✅ PASS: {len(cases)} edge-case code mappings")
    return not failures


def test_specific_mappings_cover_known_beaches(data):
    """Every specifically mapped beach exists in the coordinate tables"""
    missing = [beach for beach in SPECIFIC_POINT_MAPPINGS.values() if beach not in BEACH_COORDS]
    for beach in missing:
        print(f"❌ FAIL: Specific mapping targets unknown beach '{beach}'")
    if not missing:
        print("✅ PASS: Specific mappings target known beaches")
    return not missing


def test_beach_coverage(data):
    """The data contains exactly the beaches defined in the parser"""
    expected = set(BEACH_COORDS)
    actual = {beach['name'] for beach in data['beaches']}
    problems = []
    for name in sorted(expected - actual):
        problems.append(f"missing beach: {name}")
    for name in sorted(actual - expected):
        problems.append(f"unexpected beach: {name}")
    if len(data['beaches']) != len(actual):
        problems.append("duplicate beach names present")
    for problem in problems:
        print(f"❌ FAIL: {problem}")
    if not problems:
        print(f"✅ PASS: All {len(RJ_BEACHES)} Rio + {len(NITEROI_BEACHES)} Niterói beaches present, no extras")
    return not problems


def test_beach_fields(data):
    """Beaches carry valid statuses, coordinates, cities, and point structures"""
    problems = []
    for beach in data['beaches']:
        name = beach.get('name', '<unnamed>')
        if beach.get('status') not in VALID_STATUSES:
            problems.append(f"{name}: invalid status {beach.get('status')!r}")
        if not (LAT_BOUNDS[0] <= beach.get('lat', 0) <= LAT_BOUNDS[1]
                and LNG_BOUNDS[0] <= beach.get('lng', 0) <= LNG_BOUNDS[1]):
            problems.append(f"{name}: coordinates out of bounds ({beach.get('lat')}, {beach.get('lng')})")
        expected_city = BEACH_COORDS.get(name, {}).get('city')
        if beach.get('city') != expected_city:
            problems.append(f"{name}: city {beach.get('city')!r}, expected {expected_city!r}")
        if beach.get('status') != 'unknown' and not beach.get('lastUpdate'):
            problems.append(f"{name}: has status but no lastUpdate")
        for point in beach.get('monitoringPoints', []):
            missing = [field for field in ('code', 'location', 'status') if field not in point]
            if missing:
                problems.append(f"{name}: point missing fields {missing}")
    for problem in problems:
        print(f"❌ FAIL: {problem}")
    if not problems:
        print("✅ PASS: All beach records structurally valid")
    return not problems


def test_points_map_to_their_beach(data):
    """Each monitoring point's code maps back to the beach it is attached to"""
    problems = []
    for beach in data['beaches']:
        for point in beach.get('monitoringPoints', []):
            mapped = get_beach_from_point_code(point['code'])
            if mapped != beach['name']:
                problems.append(f"{beach['name']}: point {point['code']} maps to {mapped}")
    for problem in problems:
        print(f"❌ FAIL: {problem}")
    if not problems:
        print("✅ PASS: All monitoring points map to their beach")
    return not problems


def test_status_aggregation(data):
    """Beach status matches its points: any improper+proper mix is 'attention'"""
    problems = []
    for beach in data['beaches']:
        points = beach.get('monitoringPoints', [])
        if not points:
            continue
        proper = sum(1 for p in points if p['status'] == 'proper')
        improper = sum(1 for p in points if p['status'] == 'improper')
        if improper and proper:
            expected = 'attention'
        elif improper:
            expected = 'improper'
        elif proper:
            expected = 'proper'
        else:
            expected = 'unknown'
        if beach['status'] != expected:
            problems.append(
                f"{beach['name']}: {proper} proper / {improper} improper points"
                f" but status {beach['status']!r} (expected {expected!r})")
    for problem in problems:
        print(f"❌ FAIL: {problem}")
    if not problems:
        print("✅ PASS: Status aggregation consistent")
    return not problems


def warn_data_quality(data):
    """Non-fatal observations: unknown statuses, missing locations"""
    unknown = [b['name'] for b in data['beaches'] if b['status'] == 'unknown']
    if unknown:
        print(f"⚠️  WARNING: {len(unknown)} beaches without any known status: {unknown}")
    missing_locations = [
        f"{beach['name']}/{point['code']}"
        for beach in data['beaches']
        for point in beach.get('monitoringPoints', [])
        if not point.get('location')
    ]
    if missing_locations:
        print(f"⚠️  WARNING: {len(missing_locations)} points without location text:"
              f" {missing_locations[:5]}{'...' if len(missing_locations) > 5 else ''}")
    if not unknown and not missing_locations:
        print("ℹ️  Data quality: no unknown beaches, all points have locations")


def main():
    data_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA_FILE
    try:
        with open(data_file, encoding='utf-8') as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f"❌ ERROR: {data_file} not found. Run parse_inea_bulletin.py first.")
        sys.exit(1)

    print(f"ℹ️  Validating {data_file}")
    print(f"ℹ️  Total beaches: {len(data['beaches'])}, last update: {data.get('lastUpdate', 'N/A')}")

    tests = [
        test_point_code_normalization,
        test_edge_case_mappings,
        test_specific_mappings_cover_known_beaches,
        test_beach_coverage,
        test_beach_fields,
        test_points_map_to_their_beach,
        test_status_aggregation,
    ]

    results = []
    for test in tests:
        print(f"\n─── {test.__doc__.strip().splitlines()[0]}")
        results.append((test.__name__, test(data)))

    print()
    warn_data_quality(data)

    failed = [name for name, passed in results if not passed]
    print()
    if failed:
        print(f"⚠️  {len(results) - len(failed)}/{len(results)} tests passed, failed: {failed}")
        sys.exit(1)
    print(f"🎉 All {len(results)} tests passed!")


if __name__ == '__main__':
    main()
