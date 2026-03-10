#!/usr/bin/env python3
"""
Parse INEA beach balneability bulletin PDF and generate JSON data
"""
import subprocess
import re
import json
from datetime import datetime, timedelta

# Beach coordinates (approximate locations)
BEACH_COORDS = {
    'Barra de Guaratiba': {'lat': -23.0736, 'lng': -43.5681},
    'Grumari': {'lat': -23.0453, 'lng': -43.5247},
    'Prainha': {'lat': -23.0392, 'lng': -43.5089},
    'Pontal de Sernambetiba': {'lat': -23.0158, 'lng': -43.4897},
    'Recreio': {'lat': -23.0275, 'lng': -43.4647},
    'Recreio/Reserva': {'lat': -23.0183, 'lng': -43.4064},
    'Barra da Tijuca': {'lat': -23.0125, 'lng': -43.3642},
    'Barra da Tijuca II': {'lat': -23.0056, 'lng': -43.3319},
    'Joatinga': {'lat': -23.0089, 'lng': -43.2847},
    'Pepino': {'lat': -23.0031, 'lng': -43.2758},
    'São Conrado': {'lat': -22.9997, 'lng': -43.2689},
    'Vidigal': {'lat': -22.9944, 'lng': -43.2347},
    'Leblon': {'lat': -22.9844, 'lng': -43.2253},
    'Ipanema': {'lat': -22.9838, 'lng': -43.2044},
    'Arpoador': {'lat': -22.9875, 'lng': -43.1909},
    'Diabo': {'lat': -22.9869, 'lng': -43.1967},
    'Copacabana': {'lat': -22.9711, 'lng': -43.1822},
    'Leme': {'lat': -22.9644, 'lng': -43.1686},
    'Vermelha': {'lat': -22.9525, 'lng': -43.1675},
    'Urca': {'lat': -22.9528, 'lng': -43.1639},
    'Botafogo': {'lat': -22.9475, 'lng': -43.1764},
    'Flamengo': {'lat': -22.9344, 'lng': -43.1725},
    'Paquetá': {'lat': -22.7639, 'lng': -43.1089},
    'Ilha do Governador': {'lat': -22.8119, 'lng': -43.2056},
    'Ramos': {'lat': -22.8481, 'lng': -43.2500},
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

def parse_beach_status(text, bulletin_date):
    """Parse beach names and status from bulletin text"""
    beaches_dict = {}
    beach_id = 1
    
    lines = text.split('\n')
    
    # Parse the table - status appears after point code
    for line in lines:
        # Skip headers
        if any(x in line.upper() for x in ['BOLETIM', 'LOCALIZAÇÃO', 'PONTO', 'PRAIAS']):
            continue
        
        # Look for lines with "Própria" or "Imprópria" (case-insensitive status)
        line_upper = line.upper()
        has_propria = 'PRÓPRIA' in line_upper or 'PROPRIA' in line_upper
        has_impropria = 'IMPRÓPRIA' in line_upper or 'IMPROPRIA' in line_upper
        
        if not (has_propria or has_impropria):
            continue
        
        # Determine status
        status = 'improper' if has_impropria else 'proper'
        
        # Find which beach this line belongs to
        for beach_name in BEACH_COORDS.keys():
            # Check if beach name appears in this line (case-insensitive)
            if beach_name.upper() in line_upper or beach_name.lower() in line.lower():
                # Add or update beach
                if beach_name not in beaches_dict:
                    coords = BEACH_COORDS[beach_name]
                    beaches_dict[beach_name] = {
                        'id': beach_id,
                        'name': beach_name,
                        'lat': coords['lat'],
                        'lng': coords['lng'],
                        'status': status,
                        'zone': 'Zona Sul' if coords['lat'] > -23.01 else 'Zona Oeste',
                        'lastUpdate': bulletin_date
                    }
                    beach_id += 1
                elif status == 'improper':
                    # If any monitoring point is improper, mark beach as improper
                    beaches_dict[beach_name]['status'] = 'improper'
                break
    
    beaches = list(beaches_dict.values())
    
    # Add missing beaches as unknown
    if len(beaches) > 0:
        existing_names = {b['name'] for b in beaches}
        for beach_name, coords in BEACH_COORDS.items():
            if beach_name not in existing_names:
                beaches.append({
                    'id': beach_id,
                    'name': beach_name,
                    'lat': coords['lat'],
                    'lng': coords['lng'],
                    'status': 'unknown',
                    'zone': 'Zona Sul' if coords['lat'] > -23.01 else 'Zona Oeste',
                    'lastUpdate': bulletin_date
                })
                beach_id += 1
    
    return beaches

def parse_bulletin(pdf_path):
    """Main parsing function"""
    import os
    
    # Resolve symlink if present to get the actual filename with date
    actual_path = os.path.realpath(pdf_path) if os.path.islink(pdf_path) else pdf_path
    
    # Try to extract date from filename first (e.g., "Zona-oeste-e-Zona-sul-04-03-26.pdf")
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
        date_match = re.search(r'(\d{1,2})\s+de\s+([A-ZÇ]+)\s+de\s+(\d{4})', text)
        if date_match:
            try:
                day = date_match.group(1)
                month_pt = date_match.group(2).lower()
                year = date_match.group(3)
                months = {
                    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
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
             'zone': 'Zona Sul' if coords['lat'] > -23.01 else 'Zona Oeste'}
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
    
    pdf_file = 'latest-bulletin.pdf'
    
    # Check if PDF exists
    if not os.path.exists(pdf_file):
        print(f"✗ PDF file not found: {pdf_file}")
        sys.exit(1)
    
    # Check if PDF is valid (has content)
    if os.path.getsize(pdf_file) == 0:
        print(f"✗ PDF file is empty: {pdf_file}")
        sys.exit(1)
    
    result = parse_bulletin(pdf_file)
    
    # If parsing failed, use fallback: assume bulletin is from the last 7 days
    if not result or not result.get('beaches'):
        print("⚠️  Parsing failed, trying fallback date estimation...")
        
        # Try to extract date from filename
        filename_date_match = re.search(r'(\d{2})-(\d{2})-(\d{2})\.pdf$', pdf_file)
        if filename_date_match:
            try:
                day = int(filename_date_match.group(1))
                month = int(filename_date_match.group(2))
                year = 2000 + int(filename_date_match.group(3))
                fallback_date = datetime(year, month, day).isoformat()
            except:
                # If filename parsing fails, assume today minus a few days
                fallback_date = (datetime.now() - timedelta(days=3)).isoformat()
        else:
            # Default: 3 days ago (bulletins are typically released mid-week)
            fallback_date = (datetime.now() - timedelta(days=3)).isoformat()
        
        print(f"📅 Using fallback date: {fallback_date}")
        
        # Create minimal fallback data
        result = {
            'lastUpdate': fallback_date,
            'source': 'INEA - Instituto Estadual do Ambiente',
            'bulletin': 'Boletim de Balneabilidade das Praias',
            'beaches': [
                {'id': i+1, 'name': name, **coords, 'status': 'unknown', 
                 'zone': 'Zona Sul' if coords['lat'] > -23.01 else 'Zona Oeste',
                 'lastUpdate': fallback_date}
                for i, (name, coords) in enumerate(BEACH_COORDS.items())
            ]
        }
    
    if result:
        with open('data/beachData.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✓ Generated data/beachData.json with {len(result['beaches'])} beaches")
        print(f"✓ Last update: {result['lastUpdate']}")
    else:
        print("✗ Failed to generate data")
        sys.exit(1)
