#!/usr/bin/env python3
"""
Fetch beach water-quality statuses from INEA's public Power BI dashboard.

INEA links this dashboard from https://www.inea.rj.gov.br/balneabilidade/ as the
official "Balneabilidade de Praias" data channel. The dashboard is a public
"publish to web" report, so its backing dataset can be queried without
authentication through Power BI's public REST API. See
docs/inea-data-sources.md for how these endpoints and IDs were discovered.

Outputs normalized JSON records:
    [{"code", "beach", "city", "location", "status", "collectedAt", "lat", "lng"}, ...]
"""
import argparse
import gzip
import io
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

# The "-redirect" host rejects direct API calls; "-api" is what the embed uses.
API_HOST = 'https://wabi-brazil-south-api.analysis.windows.net'
# From the r= parameter of INEA's publish-to-web URL (decoded, key "k").
RESOURCE_KEY = '5b801b31-4f49-43f5-a91f-ece742be0290'
MODEL_ID = 5721923
DATASET_ID = 'c9353be0-85cb-4f81-9b1e-ef5e121124f7'
REPORT_ID = '642f871e-cbd8-42f4-9cd6-3536460d67c2'

ENTITY = 'fDISEQ_Balneabilidade_Praias'
# Order matters: decode_rows() zips row values against this list.
# 'Latitude ' has a trailing space in INEA's data model.
COLUMNS = [
    'Ponto de Coleta',
    'Data da coleta',
    'Praia',
    'Localização',
    'Classificação',
    'Município',
    'Latitude ',
    'Longitude',
]

CITIES = ['Rio de Janeiro', 'Niterói']

STATUS_BY_CLASSIFICATION = {
    'Própria': 'proper',
    'Imprópria': 'improper',
}

REQUEST_TIMEOUT_SECONDS = 30
MAX_ROWS = 2000


def build_query():
    select = [
        {
            'Column': {'Expression': {'SourceRef': {'Source': 'b'}}, 'Property': column},
            'Name': f'{ENTITY}.{column}',
        }
        for column in COLUMNS
    ]
    return {
        'version': '1.0.0',
        'queries': [{
            'Query': {'Commands': [{'SemanticQueryDataShapeCommand': {
                'Query': {
                    'Version': 2,
                    'From': [{'Name': 'b', 'Entity': ENTITY, 'Type': 0}],
                    'Select': select,
                },
                'Binding': {
                    'Primary': {'Groupings': [{'Projections': list(range(len(COLUMNS)))}]},
                    'DataReduction': {'DataVolume': 6, 'Primary': {'Top': {'Count': MAX_ROWS}}},
                    'Version': 1,
                },
                'ExecutionMetricsKind': 1,
            }}]},
            'CacheKey': '',
            'QueryId': '',
            'ApplicationContext': {
                'DatasetId': DATASET_ID,
                'Sources': [{'ReportId': REPORT_ID, 'VisualId': 'batheability-rio'}],
            },
        }],
        'cancelQueries': [],
        'modelId': MODEL_ID,
    }


def post_querydata(query):
    body = json.dumps(query, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        f'{API_HOST}/public/reports/querydata?synchronous=true',
        data=body,
        headers={
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip',
            'ActivityId': str(uuid.uuid4()),
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://app.powerbi.com',
            'Referer': 'https://app.powerbi.com/',
            'RequestId': str(uuid.uuid4()),
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
            'X-PowerBI-ResourceKey': RESOURCE_KEY,
        },
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        raw = response.read()
        if response.headers.get('Content-Encoding') == 'gzip':
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    return json.loads(raw)


def decode_rows(response):
    """Decode Power BI's DSR row format into plain dicts keyed by COLUMNS.

    Each row carries values only for columns that changed ("C"), with bitmask
    "R" marking columns repeated from the previous row and bitmask "Ø" marking
    nulls. String values are indices into shared ValueDicts.
    """
    data_shape = response['results'][0]['result']['data']['dsr']['DS'][0]
    if 'PH' not in data_shape:
        raise ValueError(f'Unexpected DSR shape, keys: {list(data_shape.keys())}')
    rows = data_shape['PH'][0]['DM0']
    if not rows:
        raise ValueError('Power BI returned zero rows')
    value_dicts = data_shape.get('ValueDicts', {})
    descriptors = rows[0]['S']
    if len(descriptors) != len(COLUMNS):
        raise ValueError(f'Expected {len(COLUMNS)} columns, got {len(descriptors)}')

    decoded = []
    previous = [None] * len(descriptors)
    for row in rows:
        changed = list(row.get('C', []))
        repeat_bits = row.get('R', 0)
        null_bits = row.get('Ø', 0)
        values = []
        for index in range(len(descriptors)):
            if null_bits >> index & 1:
                values.append(None)
            elif repeat_bits >> index & 1:
                values.append(previous[index])
            else:
                values.append(changed.pop(0))
        previous = values[:]

        resolved = []
        for value, descriptor in zip(values, descriptors):
            dictionary_name = descriptor.get('DN')
            if dictionary_name is not None and isinstance(value, int):
                value = value_dicts[dictionary_name][value]
            resolved.append(value)
        decoded.append(dict(zip(COLUMNS, resolved)))
    return decoded


def normalize_record(row):
    classification = row['Classificação'] or ''
    collected_at = None
    if isinstance(row['Data da coleta'], (int, float)):
        collected_at = datetime.fromtimestamp(
            row['Data da coleta'] / 1000, tz=timezone.utc
        ).date().isoformat()
    return {
        'code': row['Ponto de Coleta'],
        'beach': row['Praia'],
        'city': row['Município'],
        'location': row['Localização'],
        'status': STATUS_BY_CLASSIFICATION.get(classification, 'unknown'),
        'collectedAt': collected_at,
        'lat': row['Latitude '],
        'lng': row['Longitude'],
    }


def fetch_beach_statuses(cities):
    response = post_querydata(build_query())
    records = [normalize_record(row) for row in decode_rows(response)]
    return [record for record in records if record['city'] in cities]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='write JSON here instead of stdout')
    parser.add_argument('--cities', nargs='+', default=CITIES)
    args = parser.parse_args()

    try:
        records = fetch_beach_statuses(args.cities)
    except (urllib.error.URLError, TimeoutError) as error:
        print(f'✗ Power BI request failed: {error}', file=sys.stderr)
        sys.exit(1)
    except (KeyError, IndexError, ValueError) as error:
        print(f'✗ Power BI response format changed: {error}', file=sys.stderr)
        sys.exit(1)

    output = json.dumps(records, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as file:
            file.write(output + '\n')
    else:
        print(output)

    dates = sorted(record['collectedAt'] for record in records if record['collectedAt'])
    print(
        f'✓ Fetched {len(records)} monitoring points from Power BI'
        + (f' (collections {dates[0]} → {dates[-1]})' if dates else ''),
        file=sys.stderr,
    )


if __name__ == '__main__':
    main()
