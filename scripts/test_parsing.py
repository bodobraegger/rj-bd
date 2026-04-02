#!/usr/bin/env python3
"""
Comprehensive test script for INEA bulletin parsing.
Tests edge cases, point assignments, location extraction, and status logic.
"""

import json
import sys
from pathlib import Path

def load_beach_data():
    """Load the generated beach data JSON"""
    data_file = Path(__file__).parent.parent / 'data' / 'beachData.json'
    with open(data_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_no_unknown_beaches(data):
    """Test: All beaches should have status (no unknowns expected with current bulletins)"""
    unknown = [b for b in data['beaches'] if b['status'] == 'unknown']
    if unknown:
        print("❌ FAIL: Found unknown beaches:")
        for b in unknown:
            print(f"   - {b['name']} ({b['city']})")
        return False
    print("✅ PASS: No unknown beaches")
    return True

def test_edge_case_assignments(data):
    """Test: Edge cases are correctly assigned"""
    edge_cases = {
        'Flamengo': ['FL000', 'FL004'],
        'Glória': ['FL008'],
        'Barra da Tijuca': ['BD05', 'BD07', 'BD09'],
        'Barra da Tijuca II': ['BD10'],
        'Recreio': ['BD00', 'BD02'],
        'Recreio/Reserva': ['BD03', 'BD011'],
    }
    
    all_passed = True
    for beach_name, expected_codes in edge_cases.items():
        beach = next((b for b in data['beaches'] if b['name'] == beach_name), None)
        if not beach:
            print(f"❌ FAIL: Beach '{beach_name}' not found")
            all_passed = False
            continue
        
        actual_codes = [p['code'] for p in beach.get('monitoringPoints', [])]
        if set(actual_codes) != set(expected_codes):
            print(f"❌ FAIL: {beach_name}")
            print(f"   Expected: {expected_codes}")
            print(f"   Got: {actual_codes}")
            all_passed = False
        else:
            print(f"✅ PASS: {beach_name} -> {actual_codes}")
    
    return all_passed

def test_status_logic(data):
    """Test: Status logic (proper/improper/attention) is correct"""
    all_passed = True
    
    for beach in data['beaches']:
        points = beach.get('monitoringPoints', [])
        if not points:
            continue
        
        proper_count = sum(1 for p in points if p['status'] == 'proper')
        improper_count = sum(1 for p in points if p['status'] == 'improper')
        
        # Determine expected status
        if improper_count > 0 and proper_count > 0:
            expected_status = 'attention'
        elif improper_count > 0:
            expected_status = 'improper'
        elif proper_count > 0:
            expected_status = 'proper'
        else:
            expected_status = 'unknown'
        
        if beach['status'] != expected_status:
            print(f"❌ FAIL: {beach['name']} status logic")
            print(f"   Points: {proper_count} proper, {improper_count} improper")
            print(f"   Expected: {expected_status}, Got: {beach['status']}")
            all_passed = False
    
    if all_passed:
        print("✅ PASS: Status logic correct for all beaches")
    return all_passed

def test_location_extraction(data):
    """Test: Location text is captured for points"""
    missing_locations = []
    short_locations = []
    
    for beach in data['beaches']:
        points = beach.get('monitoringPoints', [])
        for point in points:
            location = point.get('location', '')
            if not location:
                missing_locations.append(f"{beach['name']}/{point['code']}")
            elif len(location) < 5:  # Very short locations might be truncated
                short_locations.append(f"{beach['name']}/{point['code']}: '{location}'")
    
    all_passed = True
    if missing_locations:
        print(f"⚠️  WARNING: {len(missing_locations)} points missing locations:")
        for item in missing_locations[:5]:  # Show first 5
            print(f"   - {item}")
        if len(missing_locations) > 5:
            print(f"   ... and {len(missing_locations) - 5} more")
        all_passed = False
    
    if short_locations:
        print(f"⚠️  WARNING: {len(short_locations)} points with very short locations:")
        for item in short_locations[:5]:  # Show first 5
            print(f"   - {item}")
        if len(short_locations) > 5:
            print(f"   ... and {len(short_locations) - 5} more")
    
    if all_passed:
        print("✅ PASS: All points have location text")
    return all_passed

def test_monitoring_points_structure(data):
    """Test: Monitoring points have required fields"""
    all_passed = True
    
    for beach in data['beaches']:
        points = beach.get('monitoringPoints', [])
        for point in points:
            required_fields = ['code', 'location', 'status']
            missing = [f for f in required_fields if f not in point]
            if missing:
                print(f"❌ FAIL: {beach['name']} point missing fields: {missing}")
                all_passed = False
                break
    
    if all_passed:
        print("✅ PASS: All monitoring points have required fields")
    return all_passed

def test_city_distribution(data):
    """Test: Beaches are distributed between Rio and Niterói"""
    rio_count = sum(1 for b in data['beaches'] if b['city'] == 'Rio de Janeiro')
    niteroi_count = sum(1 for b in data['beaches'] if b['city'] == 'Niterói')
    
    print(f"ℹ️  INFO: {rio_count} Rio beaches, {niteroi_count} Niterói beaches")
    
    if rio_count == 23 and niteroi_count == 14:
        print("✅ PASS: Expected beach counts (23 Rio, 14 Niterói)")
        return True
    else:
        print(f"⚠️  WARNING: Expected 23 Rio and 14 Niterói beaches")
        return False

def test_sample_locations(data):
    """Test: Show sample locations to verify quality"""
    print("\nℹ️  Sample locations (first 5 beaches with points):")
    count = 0
    for beach in data['beaches']:
        points = beach.get('monitoringPoints', [])
        if points and count < 5:
            print(f"\n   {beach['name']}:")
            for point in points[:2]:  # First 2 points per beach
                location = point.get('location', 'N/A')
                print(f"      {point['code']}: {location}")
            count += 1

def main():
    print("=" * 60)
    print("INEA Bulletin Parsing Test Suite")
    print("=" * 60)
    
    try:
        data = load_beach_data()
    except FileNotFoundError:
        print("❌ ERROR: data/beachData.json not found. Run parse_inea_bulletin.py first.")
        sys.exit(1)
    
    print(f"\nℹ️  Total beaches: {len(data['beaches'])}")
    print(f"ℹ️  Last update: {data.get('lastUpdate', 'N/A')}")
    print()
    
    tests = [
        ("No Unknown Beaches", test_no_unknown_beaches),
        ("Edge Case Assignments", test_edge_case_assignments),
        ("Status Logic", test_status_logic),
        ("Monitoring Points Structure", test_monitoring_points_structure),
        ("Location Extraction", test_location_extraction),
        ("City Distribution", test_city_distribution),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'─' * 60}")
        print(f"Test: {test_name}")
        print('─' * 60)
        passed = test_func(data)
        results.append((test_name, passed))
    
    # Show sample locations at the end
    test_sample_locations(data)
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    if passed_count == total_count:
        print(f"🎉 All {total_count} tests passed!")
        sys.exit(0)
    else:
        print(f"⚠️  {passed_count}/{total_count} tests passed")
        sys.exit(1)

if __name__ == '__main__':
    main()
