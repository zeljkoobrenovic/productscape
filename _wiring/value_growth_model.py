"""Shared Value & Growth contract, reference checks and market calculations."""
from datetime import date
from functools import lru_cache
import json
import math
from pathlib import Path
import sys
from urllib.parse import urlsplit

TOOLKIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLKIT / 'skills/scripts'))
import schema_check


@lru_cache(maxsize=1)
def value_growth_schema():
    return json.loads((TOOLKIT / '_config/_schema/value-growth.schema.json').read_text(encoding='utf-8'))


def market_totals(scenario):
    """Annual provider-revenue opportunity; SOM is a share of SAM, not TAM."""
    tam = scenario['units'] * scenario['revenuePerUnit']
    sam = tam * scenario['serviceableShare']
    return {'tam': tam, 'sam': sam, 'som': sam * scenario['obtainableShare']}


def read_optional(domain_dir, relative, default):
    path = Path(domain_dir) / relative
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def reference_catalog(domain_dir):
    people = {p['id']: p for g in read_optional(domain_dir, 'customers/customers.json', [])
              for p in g.get('customers', []) if p.get('id')}
    products = read_optional(domain_dir, 'product-deployments/products.json', {})
    competitors = read_optional(domain_dir, 'business/competition.json', {})
    return {
        'customers': people,
        'products': {p['id']: p for p in products.get('portfolio', {}).get('products', []) if p.get('id')},
        'competitors': {p['id']: p for p in competitors.get('players', []) if p.get('id')},
    }


def walk(value, path='$'):
    if isinstance(value, dict):
        yield path, value
        for key, item in value.items():
            yield from walk(item, f'{path}.{key}')
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, f'{path}[{index}]')


def validate_value_growth(payload, domain_id, domain_dir=None):
    schema = value_growth_schema()
    errors = schema_check.validate(payload, schema)
    if errors:
        return errors
    if payload['status'] == 'ready':
        schema_check.validate(payload, schema['then'], root_schema=schema, errors=errors)
    if errors:
        return errors
    if payload['domainId'] != domain_id:
        errors.append(f'$.domainId: must match the domain folder {domain_id!r}')
    sources = {s['id'] for s in payload.get('sources', [])}
    segments = {s['id'] for s in payload.get('segments', [])}
    entry_models = {m['id'] for m in payload.get('entryStrategy', {}).get('models', [])}
    catalog = reference_catalog(domain_dir) if domain_dir is not None else None

    for path, obj in walk(payload):
        for key in ('updated', 'accessed', 'published', 'observedOn'):
            if key in obj:
                try:
                    date.fromisoformat(obj[key])
                except ValueError:
                    errors.append(f'{path}.{key}: must be a real ISO date')
        for key, value in obj.items():
            if isinstance(value, list) and value and all(isinstance(v, dict) and 'id' in v for v in value):
                ids = [v['id'] for v in value]
                if len(ids) != len(set(ids)):
                    errors.append(f'{path}.{key}: duplicate ids')
        for source_id in obj.get('sourceIds', []):
            if source_id not in sources:
                errors.append(f'{path}.sourceIds: unknown source {source_id!r}')
        if obj.get('kind') in ('observed', 'inferred') and not obj.get('sourceIds'):
            errors.append(f'{path}.sourceIds: {obj["kind"]} evidence needs at least one source')
        for segment_id in obj.get('segmentIds', []):
            if segment_id not in segments:
                errors.append(f'{path}.segmentIds: unknown segment {segment_id!r}')
        for model_id in obj.get('modelIds', []):
            if model_id not in entry_models:
                errors.append(f'{path}.modelIds: unknown entry model {model_id!r}')
        if 'url' in obj:
            try:
                parsed = urlsplit(obj['url'])
                valid = (parsed.scheme in ('https', 'http') and parsed.hostname and
                         not parsed.username and not parsed.password and
                         not any(ord(c) < 33 for c in obj['url']))
                parsed.port
            except ValueError:
                valid = False
            if not valid:
                errors.append(f'{path}.url: must be an absolute HTTP(S) URL without credentials')
        if catalog:
            for field, group in (('productIds', 'products'), ('competitorIds', 'competitors')):
                for ref in obj.get(field, []):
                    if ref not in catalog[group]:
                        errors.append(f'{path}.{field}: unknown {group} reference {ref!r}')
            if 'competitorId' in obj and obj['competitorId'] not in catalog['competitors']:
                errors.append(f'{path}.competitorId: unknown competitor {obj["competitorId"]!r}')
            if 'customerId' in obj:
                person = catalog['customers'].get(obj['customerId'])
                if person is None:
                    errors.append(f'{path}.customerId: unknown customer {obj["customerId"]!r}')
                else:
                    jobs = {j['id'] for j in person.get('jobsToBeDone', [])}
                    kpis = {n['id'] for _, n in walk(person.get('kpiPyramids', {})) if 'id' in n}
                    for field, known in (('jobIds', jobs), ('kpiIds', kpis)):
                        for ref in obj.get(field, []):
                            if ref not in known:
                                errors.append(f'{path}.{field}: {ref!r} does not belong to customer {obj["customerId"]!r}')

    for index, scenario in enumerate(payload.get('market', {}).get('scenarios', [])):
        path = f'$.market.scenarios[{index}]'
        for key in ('units', 'revenuePerUnit', 'serviceableShare', 'obtainableShare'):
            value = scenario[key]
            maximum = 1 if key.endswith('Share') else float('inf')
            if not math.isfinite(value) or not 0 <= value <= maximum:
                errors.append(f'{path}.{key}: must be finite and between 0 and {maximum}')
        if not 1 <= scenario['horizonYears'] <= 30 or not 1900 <= scenario['baseYear'] <= 2200:
            errors.append(f'{path}: invalid base year or horizon')
        if not all(math.isfinite(n) for n in market_totals(scenario).values()):
            errors.append(f'{path}: calculated opportunity is too large')
    return errors
