#!/usr/bin/env python3
"""
Generate data/beachData.json from INEA balneability sources.

Sources, merged per beach with the newest data winning:
- INEA bulletin PDFs (per-zone Rio and Niterói files, see download_bulletins.sh)
- Point records from fetch_powerbi.py or parse_statewide_bulletin.py (--points-file)
- The previous beachData.json as baseline, so a beach never loses its
  last known status just because a source is unavailable this run.
"""
import argparse
import glob
import json
import re
import subprocess
import sys
from datetime import datetime

# Beach coordinates from Wikipedia (DMS converted to decimal degrees)
# Format: 'Beach Name': (lat, lng) - copy-paste directly from Google Maps
RJ_BEACHES = {
    'Barra de Guaratiba':     (-23.067535, -43.567907), # Google Maps point
    'Grumari':                (-23.049200, -43.526700), # Wide beach mid-sand
    'Prainha':                (-23.040900, -43.505700), # Surfers' sand strip
    'Pontal de Sernambetiba': (-23.031492, -43.477221), # West of the Pontal, beach point of Pontal de Sernambetiba on Google Maps
    'Recreio':                (-23.023200, -43.463200), # Posto 9 beachfront
    'Recreio/Reserva':        (-23.013526, -43.394343), # Center of the wild Reserva strip, like on Google Maps
    'Barra da Tijuca':        (-23.013241, -43.319658), # Posto 5/6 central sand
    'Barra da Tijuca II':     (-23.015138, -43.298060), # Posto 2 (Pepê area)
    'Joatinga':               (-23.015100, -43.291100), # Small cove sand strip
    'Pepino':                 (-22.999900, -43.275000), # Paragliding landing beach
    'São Conrado':            (-22.999542, -43.258539), # Near HN
    'Vidigal':                (-22.994900, -43.238400), # Sand below Sheraton hotel
    'Leblon':                 (-22.987507, -43.222320), # Posto 11 sand center
    'Ipanema':                (-22.985800, -43.204100), # Posto 9 area center
    'Arpoador':               (-22.989500, -43.191600), # User-verified baseline
    'Diabo':                  (-22.989500, -43.190600), # User-verified baseline
    'Copacabana':             (-22.970200, -43.181500), # Central sand near Posto 4
    'Leme':                   (-22.962500, -43.165800), # Center of Leme sand arc
    'Vermelha':               (-22.955500, -43.164800), # Sand at base of Sugarloaf
    'Urca':                   (-22.947946, -43.163339), # Small beach strip
    'Botafogo':               (-22.947200, -43.182200), # Central bay sand
    'Flamengo':               (-22.926500, -43.170200), # Aterro beachfront
    'Glória':                 (-22.920500, -43.169500), # Prainha da Glória curve
}

NITEROI_BEACHES = {
    'Gragoatá':      (-22.904866, -43.135232), # Sand near Forte do Gragoatá
    'Boa Viagem':    (-22.908506, -43.123000), # Narrow strip near bridge
    'Flechas':       (-22.905477, -43.121275), # Mid-sand crescent
    'Icaraí':        (-22.907366, -43.113190), # Main sand center arc
    'São Francisco': (-22.918225, -43.094941), # Bay sand area
    'Charitas':      (-22.927350, -43.096561), # Sand center by ferry
    'Jurujuba':      (-22.931233, -43.116256), # Fishing village beach, Praia do Cais GG on google maps
    'Eva':           (-22.929670, -43.122716), # Eva sand strip
    'Adão':          (-22.927632, -43.122774), # ... and adam
    'Piratininga':   (-22.958068, -43.069923), # big one
    'Sossego':       (-22.963500, -43.040500), # Secluded sand cove
    'Camboinhas':    (-22.959952, -43.064168), # Beachfront sand center
    'Itaipu':        (-22.970565, -43.045964), # Sand shore near canal
    'Itacoatiara':   (-22.974529, -43.033627), # Main surfing sand area
}

# Combined beach coordinates with city metadata
BEACH_COORDS = {
    **{name: {'lat': coords[0], 'lng': coords[1], 'city': 'Rio de Janeiro'}
       for name, coords in RJ_BEACHES.items()},
    **{name: {'lat': coords[0], 'lng': coords[1], 'city': 'Niterói'}
       for name, coords in NITEROI_BEACHES.items()},
}

DEFAULT_DATA_FILE = 'data/beachData.json'


def extract_pdf_text(pdf_path):
    """Extract text from PDF using pdftotext"""
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, '-'],
            capture_output=True,
            text=True,
            check=False  # Don't raise exception on non-zero exit
        )
        if result.returncode != 0:
            print(f"Error extracting PDF (exit code {result.returncode}): {result.stderr}")
            return None
        return result.stdout
    except FileNotFoundError:
        print("pdftotext not found. Install poppler-utils.")
        return None


def normalize_point_code(point_code):
    """Normalize a monitoring point code so different zero-padding schemes match.

    INEA's PDFs and Power BI pad codes differently ('BD03' vs 'BD003');
    both normalize to 'BD3'.
    """
    match = re.fullmatch(r'([A-Za-z]+)0*(\d+)', point_code)
    if not match:
        return point_code
    return f'{match.group(1).upper()}{match.group(2)}'


# Specific normalized-code mappings (override prefix rules)
SPECIFIC_POINT_MAPPINGS = {
    # Flamengo/Glória edge case
    'FL8': 'Glória',
    # Barra da Tijuca / Recreio / Reserva edge cases
    'BD3': 'Recreio/Reserva',
    'BD11': 'Recreio/Reserva',
    'BD5': 'Barra da Tijuca',
    'BD7': 'Barra da Tijuca',
    'BD9': 'Barra da Tijuca',
    'BD10': 'Barra da Tijuca II',
}

PREFIX_POINT_MAPPINGS = {
    'BG': 'Barra de Guaratiba',
    'GM': 'Grumari',
    'PN': 'Prainha',
    'PS': 'Pontal de Sernambetiba',
    'BD': 'Recreio',  # Default for unlisted BD codes
    'JT': 'Joatinga',
    'PP': 'Pepino',
    'GV': 'São Conrado',
    'VD': 'Vidigal',
    'LB': 'Leblon',
    'IP': 'Ipanema',
    'AR': 'Arpoador',
    'PD': 'Diabo',
    'CP': 'Copacabana',
    'LM': 'Leme',
    'VR': 'Vermelha',
    'UR': 'Urca',
    'BT': 'Botafogo',
    'FL': 'Flamengo',  # Default for unlisted FL codes
    # Niterói beaches
    'GR': 'Gragoatá',
    'BV': 'Boa Viagem',
    'FC': 'Flechas',
    'IC': 'Icaraí',
    'SF': 'São Francisco',
    'CH': 'Charitas',
    'JR': 'Jurujuba',
    'EA': 'Eva',
    'AD': 'Adão',
    'PR': 'Piratininga',
    'SG': 'Sossego',
    'CM': 'Camboinhas',
    'II': 'Itaipu',
    'IA': 'Itacoatiara',
}


def get_beach_from_point_code(point_code):
    """Map a monitoring point code to its beach name"""
    if not point_code:
        return None
    normalized = normalize_point_code(point_code)
    if normalized in SPECIFIC_POINT_MAPPINGS:
        return SPECIFIC_POINT_MAPPINGS[normalized]
    if len(normalized) < 2:
        return None
    return PREFIX_POINT_MAPPINGS.get(normalized[:2])


def get_zone(beach_name, coords):
    """Determine zone for a beach"""
    city = coords.get('city', 'Rio de Janeiro')

    if city == 'Niterói':
        return 'Niterói'

    # Rio de Janeiro zones
    if coords['lat'] > -23.01:
        return 'Zona Sul'
    else:
        return 'Zona Oeste'


def parse_monitoring_points(text, bulletin_date):
    """Extract monitoring points (code, location, status) from bulletin text"""
    monitoring_points = []
    lines = text.split('\n')
    recent_lines = []  # Keep last few lines for context

    for line in lines:
        line_stripped = line.strip()

        recent_lines.append(line)
        if len(recent_lines) > 10:
            recent_lines.pop(0)

        # Skip empty lines and headers
        if not line_stripped or any(x in line.upper() for x in ['BOLETIM', 'LOCALIZAÇÃO', 'PONTO COLETA', 'PRAIAS', 'COLETA', 'CONAMA', 'OBSERVAÇÕES', 'OBSERVACOES', 'BALNEABILIDADE']):
            continue

        line_upper = line.upper()
        has_propria = 'PRÓPRIA' in line_upper or 'PROPRIA' in line_upper
        has_impropria = 'IMPRÓPRIA' in line_upper or 'IMPROPRIA' in line_upper
        if not (has_propria or has_impropria):
            continue

        status = 'improper' if has_impropria else 'proper'

        # Extract point code if present (e.g., BG00, GM00, FL000, etc.)
        point_code_match = re.search(r'\b([A-Z]{2,3}\d{1,3})\b', line)
        point_code = point_code_match.group(1) if point_code_match else None

        # Extract location description
        # Simple approach: text between point code and status word is the location
        # Handle two cases: location before OR after point code
        location = None
        if point_code:
            for lookback in range(1, 6):  # Check last 5 lines
                test_text = ' '.join(recent_lines[-lookback:])
                test_text = re.sub(r'\s+', ' ', test_text)

                # Pattern 1: Location comes AFTER point code (e.g., "GR000 Centro da praia Própria")
                pattern_after = r'\b' + re.escape(point_code) + r'\s+(.+?)(?:\s+Pr[óo]pria|\s+Impr[óo]pria|$)'
                match = re.search(pattern_after, test_text, re.IGNORECASE)
                if match:
                    location = match.group(1).strip()
                    # Only accept if it's not just a status word
                    if location and location.lower() not in ['própria', 'propria', 'imprópria', 'impropria']:
                        break

                # Pattern 2: Location comes BEFORE point code (e.g., "Em frente à praia BG00 Própria")
                pattern_before = r'(.+?)\s+' + re.escape(point_code) + r'\s+(?:Pr[óo]pria|Impr[óo]pria)'
                match = re.search(pattern_before, test_text, re.IGNORECASE)
                if match:
                    candidate = match.group(1).strip()
                    location_match = re.search(r'((?:Em frente|Centro|Canto|Foz|Ao lado|Quebra-Mar|À\s*esquerda|À\s*direita).*)$', candidate, re.IGNORECASE)
                    if location_match:
                        location = location_match.group(1).strip()
                        break

        if location:
            location = re.sub(r'\s+', ' ', location)
            # Remove trailing point codes
            location = re.sub(r'\s+[A-Z]{2,3}\d{1,3}.*$', '', location)
            # Remove beach names that appear in the location text
            for beach_name in BEACH_COORDS.keys():
                location = location.replace(beach_name, '').strip()
            # Truncate at status words if they leaked in
            location = re.split(r'\s+(?:Própria|Imprópria|Propria|Impropria)', location, maxsplit=1)[0].strip()
            location = location.strip(' -,.')

        beach = get_beach_from_point_code(point_code)
        if beach:
            monitoring_points.append({
                'beach': beach,
                'code': point_code,
                'location': location,
                'status': status,
                'lastUpdate': bulletin_date,
            })

    return monitoring_points


def point_records_to_monitoring_points(records):
    """Convert point records (fetch_powerbi.py / parse_statewide_bulletin.py
    format) to monitoring points, skipping points outside the covered beaches
    and points without a real status."""
    monitoring_points = []
    unmapped_codes = []
    for record in records:
        if record['status'] == 'unknown' or not record['collectedAt']:
            continue
        beach = get_beach_from_point_code(record['code'])
        if not beach:
            unmapped_codes.append(record['code'])
            continue
        monitoring_points.append({
            'beach': beach,
            'code': record['code'],
            'location': record['location'],
            'status': record['status'],
            'lastUpdate': f"{record['collectedAt']}T00:00:00",
        })
    if unmapped_codes:
        print(f"ℹ️  Skipped {len(unmapped_codes)} points with unmapped codes: {sorted(set(unmapped_codes))}")
    return monitoring_points


def build_beaches(monitoring_points):
    """Aggregate monitoring points into per-beach records.

    Beach status: 'proper' (all points proper), 'improper' (all improper),
    'attention' (mixed).
    """
    beaches_by_name = {}
    for point in monitoring_points:
        name = point['beach']
        coords = BEACH_COORDS[name]
        beach = beaches_by_name.setdefault(name, {
            'name': name,
            'lat': coords['lat'],
            'lng': coords['lng'],
            'status': 'unknown',
            'city': coords['city'],
            'zone': get_zone(name, coords),
            'lastUpdate': point['lastUpdate'],
            'monitoringPoints': [],
            'properCount': 0,
            'improperCount': 0,
        })
        beach['lastUpdate'] = max(beach['lastUpdate'], point['lastUpdate'])
        if point['status'] == 'proper':
            beach['properCount'] += 1
        elif point['status'] == 'improper':
            beach['improperCount'] += 1
        beach['monitoringPoints'].append({
            'code': point['code'],
            'location': point['location'],
            'status': point['status'],
        })

    for beach in beaches_by_name.values():
        if beach['improperCount'] > 0 and beach['properCount'] > 0:
            beach['status'] = 'attention'
        elif beach['improperCount'] > 0:
            beach['status'] = 'improper'
        elif beach['properCount'] > 0:
            beach['status'] = 'proper'

    return list(beaches_by_name.values())


MONTHS_PT = {
    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'marco': 3, 'abril': 4,
    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
    'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12,
}


def extract_bulletin_date(pdf_path, text):
    """Extract the bulletin date from the filename or, failing that, the text.

    Returns an ISO datetime string, or None if no date was found.
    """
    filename_date_match = re.search(r'(\d{2})-(\d{2})-(\d{2})\.pdf$', pdf_path)
    if filename_date_match:
        day, month, short_year = (int(group) for group in filename_date_match.groups())
        try:
            return datetime(2000 + short_year, month, day).isoformat()
        except ValueError as error:
            print(f"⚠️  Could not parse date from filename: {error}")

    # Look for date pattern like "30 de MARÇO de 2026"
    date_match = re.search(r'(\d{1,2})\s+de\s+([A-ZÇÃ]+)\s+de\s+(\d{4})', text, re.IGNORECASE)
    if date_match:
        day, month_pt, year = date_match.groups()
        month = MONTHS_PT.get(month_pt.lower())
        if month:
            try:
                return datetime(int(year), month, int(day)).isoformat()
            except ValueError as error:
                print(f"⚠️  Could not parse date from PDF content: {error}")

    return None


def parse_bulletin_points(pdf_path):
    """Parse one bulletin PDF into monitoring points"""
    text = extract_pdf_text(pdf_path)
    if not text:
        return []

    bulletin_date = extract_bulletin_date(pdf_path, text)
    if bulletin_date:
        print(f"📅 Bulletin date: {bulletin_date}")
    else:
        bulletin_date = datetime.now().replace(microsecond=0).isoformat()
        print(f"⚠️  No bulletin date found, assuming today: {bulletin_date}")

    return parse_monitoring_points(text, bulletin_date)


def load_baseline_beaches(path):
    """Load beaches from the previous beachData.json, keyed by name"""
    try:
        with open(path, encoding='utf-8') as file:
            data = json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as error:
        print(f"⚠️  Ignoring unreadable baseline {path}: {error}")
        return {}
    return {beach['name']: beach for beach in data.get('beaches', [])}


def merge_beaches(baseline_by_name, source_beach_lists):
    """Merge per-beach records: newest real status wins, baseline persists.

    A beach from a source only replaces the current record when it carries an
    actual status and is at least as recent. Beaches missing everywhere are
    filled in as 'unknown' so the dataset always covers all known beaches.
    """
    merged = dict(baseline_by_name)
    for beaches in source_beach_lists:
        for beach in beaches:
            if beach['status'] == 'unknown':
                continue
            current = merged.get(beach['name'])
            if (current is None or current.get('status') == 'unknown'
                    or beach['lastUpdate'] >= current.get('lastUpdate', '')):
                merged[beach['name']] = beach

    for name, coords in BEACH_COORDS.items():
        if name not in merged:
            merged[name] = {
                'name': name,
                'lat': coords['lat'],
                'lng': coords['lng'],
                'status': 'unknown',
                'city': coords['city'],
                'zone': get_zone(name, coords),
                'lastUpdate': None,
                'monitoringPoints': [],
                'properCount': 0,
                'improperCount': 0,
            }

    final_beaches = []
    for index, beach in enumerate(sorted(merged.values(), key=lambda b: b['name']), start=1):
        beach['id'] = index
        final_beaches.append(beach)
    return final_beaches


def print_summary(beaches):
    rj_count = sum(1 for b in beaches if b['city'] == 'Rio de Janeiro')
    niteroi_count = sum(1 for b in beaches if b['city'] == 'Niterói')
    print(f"\n📊 Summary:")
    print(f"  Rio de Janeiro: {rj_count} beaches")
    print(f"  Niterói: {niteroi_count} beaches")

    print(f"\n🏖️  Status:")
    for status, label in [('proper', '✓ Proper'), ('attention', '⚠ Attention (mixed)'),
                          ('improper', '✗ Improper'), ('unknown', '? Unknown (no data)')]:
        count = sum(1 for b in beaches if b['status'] == status)
        print(f"  {label}: {count}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdfs', nargs='*',
                        help='bulletin PDFs (default: *bulletin*.pdf in . and data/)')
    parser.add_argument('--points-file', action='append', default=[],
                        help='JSON point records from fetch_powerbi.py or '
                             'parse_statewide_bulletin.py (repeatable)')
    parser.add_argument('--baseline', default=DEFAULT_DATA_FILE,
                        help='previous beachData.json to keep last known statuses from')
    parser.add_argument('--output', default=DEFAULT_DATA_FILE)
    args = parser.parse_args()

    pdf_files = sorted(set(args.pdfs or
                           glob.glob('*bulletin*.pdf') + glob.glob('data/*bulletin*.pdf')))

    source_beach_lists = []
    for pdf_file in pdf_files:
        print(f"\n📄 Processing: {pdf_file}")
        points = parse_bulletin_points(pdf_file)
        if points:
            print(f"✓ Parsed {len(points)} monitoring points")
            source_beach_lists.append(build_beaches(points))
        else:
            print(f"⚠️  No monitoring points parsed from {pdf_file}")

    for points_file in args.points_file:
        with open(points_file, encoding='utf-8') as file:
            records = json.load(file)
        points = point_records_to_monitoring_points(records)
        print(f"\n⚡ {points_file}: {len(points)} monitoring points")
        source_beach_lists.append(build_beaches(points))

    baseline_by_name = load_baseline_beaches(args.baseline)
    if not source_beach_lists and not baseline_by_name:
        print("✗ No data sources available and no baseline to fall back to")
        sys.exit(1)
    if not source_beach_lists:
        print("⚠️  No fresh sources this run; keeping baseline data")

    final_beaches = merge_beaches(baseline_by_name, source_beach_lists)

    beach_dates = [b['lastUpdate'] for b in final_beaches if b['lastUpdate']]
    final_result = {
        'lastUpdate': max(beach_dates) if beach_dates else datetime.now().replace(microsecond=0).isoformat(),
        'source': 'INEA - Instituto Estadual do Ambiente',
        'bulletin': 'Boletim de Balneabilidade das Praias',
        'beaches': final_beaches,
    }

    with open(args.output, 'w', encoding='utf-8') as file:
        json.dump(final_result, file, ensure_ascii=False, indent=2)

    print(f"\n✓ Generated {args.output} with {len(final_beaches)} beaches")
    print(f"✓ Last update: {final_result['lastUpdate']}")
    print_summary(final_beaches)


if __name__ == '__main__':
    main()
