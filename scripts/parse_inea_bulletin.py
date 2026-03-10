#!/usr/bin/env python3
"""
Parse INEA beach balneability bulletin PDF and generate JSON data
"""
import subprocess
import re
import json
from datetime import datetime

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
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error extracting PDF: {e}")
        return None
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
    text = extract_pdf_text(pdf_path)
    if not text:
        return None
    
    # Extract date from bulletin
    date_match = re.search(r'(\d{1,2})\s+de\s+([A-ZÇ]+)\s+de\s+(\d{4})', text)
    bulletin_date = datetime.now().isoformat()
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
        except:
            pass
    
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
    result = parse_bulletin('latest-bulletin.pdf')
    if result:
        with open('data/beachData.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✓ Generated data/beachData.json with {len(result['beaches'])} beaches")
        print(f"✓ Last update: {result['lastUpdate']}")
    else:
        print("✗ Failed to parse bulletin")
