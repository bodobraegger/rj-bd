#!/usr/bin/env python3
"""
Parse INEA beach balneability bulletin PDF and generate JSON data
"""
import subprocess
import re
import json
from datetime import datetime, timedelta

# Beach coordinates (approximate locations)
# Format: 'Beach Name': (lat, lng) - copy-paste directly from Google Maps
RJ_BEACHES = {
    'Barra de Guaratiba':     (-23.073600, -43.568100),
    'Grumari':                (-23.045300, -43.524700),
    'Prainha':                (-23.039200, -43.508900),
    'Pontal de Sernambetiba': (-23.015800, -43.489700),
    'Recreio':                (-23.027500, -43.464700),
    'Recreio/Reserva':        (-23.018300, -43.406400),
    'Barra da Tijuca':        (-23.012500, -43.364200),
    'Barra da Tijuca II':     (-23.005600, -43.331900),
    'Joatinga':               (-23.008900, -43.284700),
    'Pepino':                 (-23.003100, -43.275800),
    'São Conrado':            (-22.999700, -43.268900),
    'Vidigal':                (-22.994400, -43.234700),
    'Leblon':                 (-22.984400, -43.225300),
    'Ipanema':                (-22.983800, -43.204400),
    'Arpoador':               (-22.987500, -43.190900),
    'Diabo':                  (-22.989500, -43.190600),
    'Copacabana':             (-22.971100, -43.182200),
    'Leme':                   (-22.964400, -43.168600),
    'Vermelha':               (-22.952500, -43.167500),
    'Urca':                   (-22.952800, -43.163900),
    'Botafogo':               (-22.947500, -43.176400),
    'Flamengo':               (-22.934400, -43.172500),
    'Glória':                 (-22.921100, -43.171900),
}

NITEROI_BEACHES = {
    'Gragoatá':      (-22.900600, -43.128600),
    'Boa Viagem':    (-22.896700, -43.125800),
    'Flechas':       (-22.895600, -43.118600),
    'Icaraí':        (-22.905800, -43.105000),
    'São Francisco': (-22.914400, -43.100000),
    'Charitas':      (-22.925000, -43.093100),
    'Jurujuba':      (-22.935800, -43.085000),
    'Eva':           (-22.950000, -43.033300),
    'Adão':          (-22.949200, -43.031900),
    'Piratininga':   (-22.955000, -43.073300),
    'Sossego':       (-22.962200, -43.038300),
    'Camboinhas':    (-22.951700, -43.023100),
    'Itaipu':        (-22.965800, -43.028900),
    'Itacoatiara':   (-22.981100, -43.030600),
}

# Combined beach coordinates with city metadata
BEACH_COORDS = {
    **{name: {'lat': coords[0], 'lng': coords[1], 'city': 'Rio de Janeiro'} 
       for name, coords in RJ_BEACHES.items()},
    **{name: {'lat': coords[0], 'lng': coords[1], 'city': 'Niterói'} 
       for name, coords in NITEROI_BEACHES.items()},
}

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

# Point code to beach name mapping
# Handles specific codes and prefix patterns based on INEA bulletin conventions
def get_beach_from_point_code(point_code):
    """Map a point code to its beach name, handling edge cases"""
    if not point_code:
        return None
    
    # Specific code mappings (override prefix rules)
    specific_mappings = {
        # Flamengo/Glória edge case
        'FL008': 'Glória',
        # Barra da Tijuca / Recreio / Reserva edge cases
        'BD03': 'Recreio/Reserva',
        'BD011': 'Recreio/Reserva',
        'BD05': 'Barra da Tijuca',
        'BD07': 'Barra da Tijuca',
        'BD09': 'Barra da Tijuca',
        'BD10': 'Barra da Tijuca II',
    }
    
    if point_code in specific_mappings:
        return specific_mappings[point_code]
    
    # Default prefix mappings
    prefix = point_code[:2] if len(point_code) >= 2 else None
    if not prefix:
        return None
    
    prefix_mappings = {
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
    
    return prefix_mappings.get(prefix)

def normalize_text(text):
    """Normalize text for comparison - handle accents and special chars"""
    replacements = {
        'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A',
        'É': 'E', 'È': 'E', 'Ê': 'E',
        'Í': 'I', 'Ì': 'I', 'Î': 'I',
        'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O',
        'Ú': 'U', 'Ù': 'U', 'Û': 'U',
        'Ç': 'C',
    }
    result = text.upper()
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result

def parse_beach_status(text, bulletin_date):
    """Parse beach names and status from bulletin text - track individual monitoring points"""
    monitoring_points = []  # Track each point separately
    point_id = 1
    
    lines = text.split('\n')
    recent_lines = []  # Keep last few lines for context
    
    # Parse the table - status appears after point code
    for line in lines:
        line_stripped = line.strip()
        
        # Keep track of recent lines (last 10 lines to catch beach names that appear earlier)
        recent_lines.append(line)
        if len(recent_lines) > 10:
            recent_lines.pop(0)
        
        # Skip empty lines and headers
        if not line_stripped or any(x in line.upper() for x in ['BOLETIM', 'LOCALIZAÇÃO', 'PONTO COLETA', 'PRAIAS', 'COLETA', 'CONAMA', 'OBSERVAÇÕES', 'OBSERVACOES', 'BALNEABILIDADE']):
            continue
        
        # Look for lines with "Própria" or "Imprópria" (case-insensitive status)
        line_upper = line.upper()
        has_propria = 'PRÓPRIA' in line_upper or 'PROPRIA' in line_upper
        has_impropria = 'IMPRÓPRIA' in line_upper or 'IMPROPRIA' in line_upper
        
        if not (has_propria or has_impropria):
            # Check if this line contains a beach name (update current_beach)
            # Only match if beach name appears standalone (not as substring of another beach)
            # Sort by length to check longer names first (e.g., "Barra de Guaratiba" before "Guaratiba")
            sorted_beaches = sorted(BEACH_COORDS.keys(), key=len, reverse=True)
            for beach_name in sorted_beaches:
                beach_normalized = normalize_text(beach_name)
                line_normalized = normalize_text(line)
                
                # Check if beach name appears in this line
                # Use word boundary check to avoid matching "Guaratiba" in "Barra de Guaratiba"
                if beach_normalized in line_normalized:
                    # Verify it's not part of a longer beach name by checking if we already matched a longer one
                    # If this beach name is a substring of another, skip it
                    is_substring = False
                    for other_beach in sorted_beaches:
                        if other_beach == beach_name:
                            continue
                        other_normalized = normalize_text(other_beach)
                        # If this beach is a substring of another beach that also appears in the line, skip it
                        if beach_normalized in other_normalized and other_normalized in line_normalized:
                            is_substring = True
                            break
                    
                    if not is_substring:
                        current_beach = beach_name
                        break
            continue
        
        # Determine status
        status = 'improper' if has_impropria else 'proper'
        
        # Extract point code if present (e.g., BG00, GM00, FL000, etc.)
        point_code_match = re.search(r'\b([A-Z]{2,3}\d{1,3})\b', line)
        point_code = point_code_match.group(1) if point_code_match else None
        
        # Get point prefix (letters only)
        point_prefix = None
        if point_code:
            point_prefix = ''.join([c for c in point_code if c.isalpha()])
        
        # Extract location description
        # Simple approach: text between point code and status word is the location
        # Handle two cases: location before OR after point code
        location = None
        if point_code:  # Only if we have a point code
            for lookback in range(1, 6):  # Check last 5 lines
                test_text = ' '.join(recent_lines[-lookback:])
                # Clean up whitespace
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
                    # Extract just the location part (after any beach names or other text)
                    # Look for common location keywords
                    location_match = re.search(r'((?:Em frente|Centro|Canto|Foz|Ao lado|Quebra-Mar|À\s*esquerda|À\s*direita).*)$', candidate, re.IGNORECASE)
                    if location_match:
                        location = location_match.group(1).strip()
                        break
        
        # Clean up location if found
        if location:
            # Normalize whitespace
            location = re.sub(r'\s+', ' ', location)
            # Remove trailing point codes
            location = re.sub(r'\s+[A-Z]{2,3}\d{1,3}.*$', '', location)
            # Remove beach names that appear in the location text
            for beach_name in BEACH_COORDS.keys():
                location = location.replace(beach_name, '').strip()
            # Truncate at status words if they leaked in
            location = re.split(r'\s+(?:Própria|Imprópria|Propria|Impropria)', location, maxsplit=1)[0].strip()
            # Remove leading/trailing punctuation artifacts
            location = location.strip(' -,.')
        
        # Find which beach this line belongs to using point code
        found_beach = None
        if point_code:
            found_beach = get_beach_from_point_code(point_code)
        
        # Add monitoring point
        if found_beach:
            coords = BEACH_COORDS[found_beach]
            city = coords.get('city', 'Rio de Janeiro')
            
            monitoring_points.append({
                'id': point_id,
                'beach': found_beach,
                'code': point_code,
                'location': location,
                'status': status,
                'lat': coords['lat'],
                'lng': coords['lng'],
                'city': city,
                'zone': get_zone(found_beach, coords),
                'lastUpdate': bulletin_date
            })
            point_id += 1
    
    # Now aggregate monitoring points into beaches
    # A beach status can be: 'proper' (all points proper), 'improper' (any point improper), or 'attention' (mixed)
    beaches_dict = {}
    beach_id = 1
    
    for point in monitoring_points:
        beach_name = point['beach']
        
        if beach_name not in beaches_dict:
            beaches_dict[beach_name] = {
                'id': beach_id,
                'name': beach_name,
                'lat': point['lat'],
                'lng': point['lng'],
                'status': point['status'],
                'city': point['city'],
                'zone': point['zone'],
                'lastUpdate': bulletin_date,
                'monitoringPoints': [],  # Store monitoring points
                'properCount': 0,
                'improperCount': 0
            }
            beach_id += 1
        
        # Count point statuses
        if point['status'] == 'proper':
            beaches_dict[beach_name]['properCount'] += 1
        elif point['status'] == 'improper':
            beaches_dict[beach_name]['improperCount'] += 1
        
        # Add monitoring point info
        beaches_dict[beach_name]['monitoringPoints'].append({
            'code': point['code'],
            'location': point['location'],
            'status': point['status']
        })
    
    # Determine final beach status based on points
    for beach in beaches_dict.values():
        if beach['improperCount'] > 0 and beach['properCount'] > 0:
            # Mixed status - some points proper, some improper
            beach['status'] = 'attention'
        elif beach['improperCount'] > 0:
            # All measured points are improper
            beach['status'] = 'improper'
        elif beach['properCount'] > 0:
            # All measured points are proper
            beach['status'] = 'proper'
        else:
            beach['status'] = 'unknown'
    
    beaches = list(beaches_dict.values())
    
    # Add missing beaches as unknown (grey on map - no data available)
    existing_names = {b['name'] for b in beaches}
    for beach_name, coords in BEACH_COORDS.items():
        if beach_name not in existing_names:
            city = coords.get('city', 'Rio de Janeiro')
            beaches.append({
                'id': beach_id,
                'name': beach_name,
                'lat': coords['lat'],
                'lng': coords['lng'],
                'status': 'unknown',
                'city': city,
                'zone': get_zone(beach_name, coords),
                'lastUpdate': bulletin_date,
                'monitoringPoints': [],
                'properCount': 0,
                'improperCount': 0
            })
            beach_id += 1
    
    return beaches

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

def parse_bulletin(pdf_path):
    """Main parsing function"""
    import os
    
    # Resolve symlink if present to get the actual filename with date
    actual_path = os.path.realpath(pdf_path) if os.path.islink(pdf_path) else pdf_path
    
    # Try to extract date from filename first (e.g., "Zona-sudoeste-e-Zona-sul-30-03-26.pdf" or "Niterói-30-03-26.pdf")
    bulletin_date = datetime.now().isoformat()
    filename_date_match = re.search(r'(\d{2})-(\d{2})-(\d{2})\.pdf$', actual_path)
    if filename_date_match:
        try:
            day = int(filename_date_match.group(1))
            month = int(filename_date_match.group(2))
            year = 2000 + int(filename_date_match.group(3))  # Assuming 20xx
            bulletin_date = datetime(year, month, day).isoformat()
            print(f"📅 Extracted date from filename: {bulletin_date}")
        except Exception as e:
            print(f"⚠️  Could not parse date from filename: {e}")
    
    text = extract_pdf_text(pdf_path)
    if not text:
        return None
    
    # If filename date didn't work, try extracting from PDF content
    if bulletin_date == datetime.now().isoformat():
        # Look for date pattern like "30 de MARÇO de 2026"
        date_match = re.search(r'(\d{1,2})\s+de\s+([A-ZÇÃ]+)\s+de\s+(\d{4})', text, re.IGNORECASE)
        if date_match:
            try:
                day = date_match.group(1)
                month_pt = date_match.group(2).lower()
                year = date_match.group(3)
                months = {
                    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'marco': 3, 'abril': 4,
                    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
                    'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
                }
                month = months.get(month_pt, 1)
                bulletin_date = datetime(int(year), month, int(day)).isoformat()
                print(f"📅 Extracted date from PDF content: {bulletin_date}")
            except Exception as e:
                print(f"⚠️  Could not parse date from PDF content: {e}")
    
    beaches = parse_beach_status(text, bulletin_date)
    
    # If we didn't get beaches from parsing, use defaults with coordinates
    if not beaches:
        print("Warning: Could not parse beach data from PDF. Using defaults.")
        beaches = [
            {'id': i+1, 'name': name, **coords, 'status': 'unknown', 
             'city': coords.get('city', 'Rio de Janeiro'),
             'zone': get_zone(name, coords)}
            for i, (name, coords) in enumerate(BEACH_COORDS.items())
        ]
    
    return {
        'lastUpdate': bulletin_date,
        'source': 'INEA - Instituto Estadual do Ambiente',
        'bulletin': 'Boletim de Balneabilidade das Praias',
        'beaches': beaches
    }

if __name__ == '__main__':
    import sys
    import os
    import glob
    
    # Look for all bulletin PDFs
    # First check if files were passed as arguments
    if len(sys.argv) > 1:
        pdf_files = [arg for arg in sys.argv[1:] if arg.endswith('.pdf')]
    else:
        # Look in current directory and data/ subdirectory
        pdf_files = (glob.glob('*bulletin*.pdf') + glob.glob('*-26.pdf') + 
                     glob.glob('data/*bulletin*.pdf') + glob.glob('data/*-26.pdf'))
    
    if not pdf_files:
        print(f"✗ No PDF bulletin files found")
        sys.exit(1)
    
    all_beaches = []
    latest_date = None
    
    # Parse each bulletin
    for pdf_file in pdf_files:
        print(f"\n📄 Processing: {pdf_file}")
        
        # Check if PDF is valid (has content)
        if not os.path.exists(pdf_file):
            print(f"✗ PDF file not found: {pdf_file}")
            continue
            
        if os.path.getsize(pdf_file) == 0:
            print(f"✗ PDF file is empty: {pdf_file}")
            continue
        
        result = parse_bulletin(pdf_file)
        
        if result and result.get('beaches'):
            print(f"✓ Parsed {len(result['beaches'])} beaches from {pdf_file}")
            
            # Track the latest update date
            if not latest_date or result['lastUpdate'] > latest_date:
                latest_date = result['lastUpdate']
            
            # Add beaches from this bulletin
            all_beaches.extend(result['beaches'])
        else:
            print(f"⚠️  Could not parse beaches from {pdf_file}")
    
    if not all_beaches:
        print("\n✗ No beaches parsed from any bulletin")
        sys.exit(1)
    
    # Remove duplicates (keep the one with most recent status info)
    beaches_by_name = {}
    for beach in all_beaches:
        name = beach['name']
        if name not in beaches_by_name:
            beaches_by_name[name] = beach
        elif beach['status'] != 'unknown' and beaches_by_name[name]['status'] == 'unknown':
            # Prefer beaches with actual status over unknown
            beaches_by_name[name] = beach
    
    # Reassign IDs
    final_beaches = []
    for idx, beach in enumerate(sorted(beaches_by_name.values(), key=lambda x: x['name']), start=1):
        beach['id'] = idx
        final_beaches.append(beach)
    
    # Create final result
    final_result = {
        'lastUpdate': latest_date or datetime.now().isoformat(),
        'source': 'INEA - Instituto Estadual do Ambiente',
        'bulletin': 'Boletim de Balneabilidade das Praias',
        'beaches': final_beaches
    }
    
    # Write to file
    with open('data/beachData.json', 'w', encoding='utf-8') as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Generated data/beachData.json with {len(final_beaches)} beaches")
    print(f"✓ Last update: {final_result['lastUpdate']}")
    
    # Print summary by city
    rj_beaches = [b for b in final_beaches if b.get('city') == 'Rio de Janeiro']
    niteroi_beaches = [b for b in final_beaches if b.get('city') == 'Niterói']
    
    print(f"\n📊 Summary:")
    print(f"  Rio de Janeiro: {len(rj_beaches)} beaches")
    print(f"  Niterói: {len(niteroi_beaches)} beaches")
    
    # Status summary
    proper = len([b for b in final_beaches if b['status'] == 'proper'])
    improper = len([b for b in final_beaches if b['status'] == 'improper'])
    attention = len([b for b in final_beaches if b['status'] == 'attention'])
    unknown = len([b for b in final_beaches if b['status'] == 'unknown'])
    
    print(f"\n🏖️  Status:")
    print(f"  ✓ Proper: {proper}")
    print(f"  ⚠ Attention (mixed): {attention}")
    print(f"  ✗ Improper: {improper}")
    print(f"  ? Unknown: {unknown}")
