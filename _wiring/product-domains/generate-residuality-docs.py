import json
import os
import re

from domain_cli import load_domain_args
from generator_common import template_path
from generator_common import (
    domain_docs_path,
    domain_source_path,
    copy_files_into,
    copy_icons,
    enter_docs_root,
    load_json_if_exists,
    read_import,
    render_breadcrumbs,
    reset_output_folder,
    today_string,
)

TEMPLATES_ROOT = template_path('residuality')

TARGET_TYPES = {
    'vision',
    'job',
    'journey',
    'kpi',
    'product',
    'stream',
    'brick',
    'team',
    'competitor',
}
RESIDUE_STATUSES = {'candidate', 'integrated', 'already-survived'}
FORBIDDEN_STRESSOR_FIELDS = {'probability', 'likelihood'}


def slugify(value):
    value = re.sub(r'[^a-z0-9]+', '-', str(value or '').lower()).strip('-')
    return value or 'step'


def load_domain_json(domain_id, relative_path, default_value):
    return load_json_if_exists(domain_source_path(domain_id, relative_path), default_value)


def add_catalog_item(items, target_type, target_id, name, description='', href='', context=''):
    if not target_id or not name:
        return
    items.append({
        'type': target_type,
        'id': str(target_id),
        'name': str(name),
        'description': str(description or ''),
        'href': href,
        'context': str(context or ''),
    })


def collect_kpi_items(node, customer, items, seen):
    if isinstance(node, list):
        for child in node:
            collect_kpi_items(child, customer, items, seen)
        return
    if not isinstance(node, dict):
        return

    item_id = node.get('id')
    item_name = node.get('name')
    if item_id and item_name:
        target_id = customer['id'] + '/' + str(item_id)
        if target_id not in seen:
            seen.add(target_id)
            add_catalog_item(
                items,
                'kpi',
                target_id,
                item_name,
                node.get('description', ''),
                '../customers/landing_pages/' + customer['id'] + '.html',
                customer.get('name', customer['id']),
            )

    for value in node.values():
        if isinstance(value, (dict, list)):
            collect_kpi_items(value, customer, items, seen)


def collect_items_in_named_arrays(node, key, target_type, href_prefix, items, seen):
    if isinstance(node, list):
        for child in node:
            collect_items_in_named_arrays(child, key, target_type, href_prefix, items, seen)
        return
    if not isinstance(node, dict):
        return

    values = node.get(key)
    if isinstance(values, list):
        for value in values:
            if not isinstance(value, dict):
                continue
            item_id = value.get('id')
            item_name = value.get('name') or value.get('title')
            if item_id and item_name and item_id not in seen:
                seen.add(item_id)
                add_catalog_item(
                    items,
                    target_type,
                    item_id,
                    item_name,
                    value.get('description', ''),
                    href_prefix + str(item_id) + '.html',
                    value.get('type', ''),
                )

    for value in node.values():
        if isinstance(value, (dict, list)):
            collect_items_in_named_arrays(value, key, target_type, href_prefix, items, seen)


def build_catalog(customers, products_payload, bricks_payload, streams_payload, teams_payload, competition_payload):
    items = []

    for group in customers if isinstance(customers, list) else []:
        for customer in group.get('customers', []):
            customer_id = str(customer.get('id', ''))
            customer_name = customer.get('name', customer_id)
            customer_href = '../customers/landing_pages/' + customer_id + '.html'
            strategy = customer.get('productStrategy', {})
            add_catalog_item(
                items,
                'vision',
                customer_id,
                customer_name + ' product vision',
                strategy.get('vision', ''),
                customer_href,
                group.get('group', ''),
            )

            for job in customer.get('jobsToBeDone', []):
                job_id = str(job.get('id', ''))
                canonical_job_id = customer_id + '/' + job_id
                add_catalog_item(
                    items,
                    'job',
                    canonical_job_id,
                    job.get('name', job_id),
                    job.get('whatItIs', ''),
                    customer_href,
                    customer_name,
                )
                for step in job.get('steps', []):
                    step_name = step.get('step') or step.get('name') or step.get('title')
                    add_catalog_item(
                        items,
                        'journey',
                        canonical_job_id + '/' + slugify(step_name),
                        step_name,
                        step.get('description', ''),
                        customer_href,
                        job.get('name', job_id),
                    )

            collect_kpi_items(customer.get('kpiPyramids', {}), customer, items, set())

    products = products_payload.get('portfolio', {}).get('products', []) if isinstance(products_payload, dict) else []
    for product in products:
        product_id = product.get('id')
        add_catalog_item(
            items,
            'product',
            product_id,
            product.get('name', product_id),
            product.get('description', ''),
            '../product-deployments/landing_pages/' + str(product_id) + '.html',
            product.get('type', ''),
        )

    collect_items_in_named_arrays(
        bricks_payload,
        'bricks',
        'brick',
        '../product-bricks/landing_pages/',
        items,
        set(),
    )
    collect_items_in_named_arrays(
        streams_payload,
        'streams',
        'stream',
        '../product-bricks/stream_pages/',
        items,
        set(),
    )
    collect_items_in_named_arrays(
        teams_payload,
        'teams',
        'team',
        '../teams/landing_pages/',
        items,
        set(),
    )

    players = competition_payload.get('players', []) if isinstance(competition_payload, dict) else []
    for player in players:
        player_id = player.get('id')
        add_catalog_item(
            items,
            'competitor',
            player_id,
            player.get('name', player_id),
            player.get('description', ''),
            '../competition/landing_pages/' + str(player_id) + '.html',
            player.get('category', '').replace('_', ' '),
        )

    deduplicated = {}
    for item in items:
        deduplicated.setdefault((item['type'], item['id']), item)
    return list(deduplicated.values())


def normalized_field_name(value):
    return re.sub(r'[^a-z]', '', str(value).lower())


def find_forbidden_fields(value, path='stressor'):
    problems = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = normalized_field_name(key)
            if any(forbidden in normalized for forbidden in FORBIDDEN_STRESSOR_FIELDS):
                problems.append(path + '.' + str(key))
            problems.extend(find_forbidden_fields(child, path + '.' + str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            problems.extend(find_forbidden_fields(child, path + '[' + str(index) + ']'))
    return problems


def validate_model(model, catalog):
    if not isinstance(model, dict):
        raise ValueError('residuality/residuality.json must contain an object')
    metadata = model.get('metadata')
    if not isinstance(metadata, dict):
        raise ValueError('residuality.metadata must be an object')
    stressors = model.get('stressors', [])
    if not isinstance(stressors, list):
        raise ValueError('residuality.stressors must be an array')

    catalog_keys = {(item['type'], item['id']) for item in catalog}
    stressor_ids = set()
    stressor_lookup = {}
    stressor_positions = {}
    problems = []

    for field in ('title', 'description', 'modelVersion', 'naiveArchitecture', 'residualArchitecture'):
        if not metadata.get(field):
            problems.append('metadata.' + field + ' is required')

    for index, stressor in enumerate(stressors):
        prefix = 'stressors[' + str(index) + ']'
        if not isinstance(stressor, dict):
            problems.append(prefix + ' must be an object')
            continue

        stressor_id = str(stressor.get('id', ''))
        if not stressor_id:
            problems.append(prefix + '.id is required')
        elif stressor_id != stressor_id.lower():
            problems.append(prefix + '.id must be lowercase')
        elif not re.match(r'^[a-z0-9][a-z0-9_-]*$', stressor_id):
            problems.append(prefix + '.id must contain only lowercase letters, numbers, hyphens, or underscores')
        elif stressor_id in stressor_ids:
            problems.append(prefix + '.id duplicates ' + stressor_id)
        stressor_ids.add(stressor_id)
        stressor_lookup[stressor_id] = stressor
        stressor_positions[stressor_id] = index

        for field in ('name', 'group', 'detection', 'attractor', 'businessReaction', 'residue'):
            if not stressor.get(field):
                problems.append(prefix + '.' + field + ' is required')

        if 'status' not in stressor:
            problems.append(prefix + '.status is required')
        status = stressor.get('status', 'candidate')
        if status not in RESIDUE_STATUSES:
            problems.append(prefix + '.status must be one of ' + ', '.join(sorted(RESIDUE_STATUSES)))

        if 'impacts' not in stressor:
            problems.append(prefix + '.impacts is required')
        impacts = stressor.get('impacts', [])
        if not isinstance(impacts, list):
            problems.append(prefix + '.impacts must be an array')
            impacts = []
        for impact_index, impact in enumerate(impacts):
            impact_prefix = prefix + '.impacts[' + str(impact_index) + ']'
            if not isinstance(impact, dict):
                problems.append(impact_prefix + ' must be an object')
                continue
            target_type = impact.get('targetType')
            target_id = impact.get('targetId')
            if target_type not in TARGET_TYPES:
                problems.append(impact_prefix + '.targetType is unknown: ' + str(target_type))
            elif (target_type, target_id) not in catalog_keys:
                problems.append(impact_prefix + ' does not resolve: ' + str(target_type) + ':' + str(target_id))
            if isinstance(target_id, str) and target_id != target_id.lower():
                problems.append(impact_prefix + '.targetId must be lowercase')
            if not impact.get('effect'):
                problems.append(impact_prefix + '.effect is required')

        forbidden_fields = find_forbidden_fields(stressor, prefix)
        for field_path in forbidden_fields:
            problems.append(
                field_path
                + ' is forbidden: residuality does not assign probability or likelihood; describe the attractor instead'
            )

    for index, stressor in enumerate(stressors):
        reused_ids = stressor.get('reusesResidueIds', [])
        if not isinstance(reused_ids, list):
            problems.append('stressors[' + str(index) + '].reusesResidueIds must be an array')
            reused_ids = []
        elif any(not isinstance(reused_id, str) for reused_id in reused_ids):
            problems.append('stressors[' + str(index) + '].reusesResidueIds must contain only strings')
            reused_ids = [reused_id for reused_id in reused_ids if isinstance(reused_id, str)]
        elif len(set(reused_ids)) != len(reused_ids):
            problems.append('stressors[' + str(index) + '].reusesResidueIds must not contain duplicates')
        if stressor.get('status') == 'already-survived' and not reused_ids:
            problems.append('stressors[' + str(index) + '] is already-survived but reuses no earlier residue')
        for reused_id in reused_ids:
            if reused_id not in stressor_ids:
                problems.append(
                    'stressors[' + str(index) + '].reusesResidueIds does not resolve: ' + str(reused_id)
                )
            elif stressor_lookup.get(reused_id, {}).get('status', 'candidate') == 'candidate':
                problems.append(
                    'stressors[' + str(index) + '].reusesResidueIds points to candidate residue: ' + str(reused_id)
                )
            elif stressor_positions.get(reused_id, index) >= index:
                problems.append(
                    'stressors[' + str(index) + '].reusesResidueIds must point to an earlier residue: ' + str(reused_id)
                )

    test = model.get('freshStressorTest')
    if test is not None:
        if not isinstance(test, dict):
            problems.append('freshStressorTest must be an object')
        else:
            total = test.get('stressors')
            naive = test.get('naiveSurvivals')
            residual = test.get('residualSurvivals')
            if not isinstance(total, int) or total <= 0:
                problems.append('freshStressorTest.stressors must be a positive integer')
            if not isinstance(naive, int) or naive < 0:
                problems.append('freshStressorTest.naiveSurvivals must be a non-negative integer')
            if not isinstance(residual, int) or residual < 0:
                problems.append('freshStressorTest.residualSurvivals must be a non-negative integer')
            if isinstance(total, int) and total > 0:
                if isinstance(naive, int) and naive > total:
                    problems.append('freshStressorTest.naiveSurvivals cannot exceed stressors')
                if isinstance(residual, int) and residual > total:
                    problems.append('freshStressorTest.residualSurvivals cannot exceed stressors')

    if problems:
        raise ValueError('Invalid residuality model:\n- ' + '\n- '.join(problems))


def default_model(domain):
    return {
        'metadata': {
            'title': domain['name'] + ' Residuality Stress Test',
            'description': 'Explore how this product would need to change when customers, markets, regulation, operations, or competitors behave differently from today\'s assumptions.',
            'modelVersion': '1.0',
            'naiveArchitecture': 'Not authored yet. Describe the simplest product and architecture that satisfies the currently stated problem.',
            'residualArchitecture': 'Not authored yet. Combine the useful changes into one coherent, more adaptable product and architecture.',
            'note': 'Add residuality/residuality.json to this domain. Begin with a credible outside change and describe the concrete business and product response.',
            'source': {
                'title': 'Residues: Time, Change, and Uncertainty in Software Architecture',
                'author': "Barry M. O'Reilly",
                'year': '2024',
                'url': 'https://leanpub.com/residuality',
            },
        },
        'stressors': [],
    }


def json_for_script(value):
    return json.dumps(value).replace('</', '<\\/')


def create_docs(domain):
    domain_id = domain['id']
    model = load_domain_json(domain_id, 'residuality/residuality.json', default_model(domain))
    customers = load_domain_json(domain_id, 'customers/customers.json', [])
    products = load_domain_json(domain_id, 'product-deployments/products.json', {})
    bricks = load_domain_json(domain_id, 'product-bricks/product-bricks.json', {})
    streams = load_domain_json(domain_id, 'product-bricks/product-stream.json', {})
    teams = load_domain_json(domain_id, 'teams/teams.json', {})
    competition = load_domain_json(domain_id, 'business/competition.json', {})

    catalog = build_catalog(customers, products, bricks, streams, teams, competition)
    validate_model(model, catalog)

    docs_folder = domain_docs_path(domain_id, 'residuality') + '/'
    reset_output_folder(docs_folder, 'icons', 'media')
    copy_icons(TEMPLATES_ROOT + 'icons', docs_folder)
    copy_files_into(
        domain_source_path(domain_id, 'residuality', 'media'),
        os.path.join(docs_folder, 'media'),
    )

    template = open(TEMPLATES_ROOT + 'index.html').read()
    app_style = open(TEMPLATES_ROOT + 'style.css').read()
    app_script = open(TEMPLATES_ROOT + 'app.js').read()
    tokens_style = read_import(TEMPLATES_ROOT, 'tokens/style')
    tabs_style = read_import(TEMPLATES_ROOT, 'tabs/style')
    breadcrumbs_style = read_import(TEMPLATES_ROOT, 'breadcrumbs/style')
    breadcrumbs_script = read_import(TEMPLATES_ROOT, 'breadcrumbs/script')
    breadcrumbs = render_breadcrumbs(TEMPLATES_ROOT, 'index_breadcrumbs.json', {
        'domain_name': domain['name'],
    })
    rendered = (
        template
        .replace('${tokens_style}', tokens_style)
        .replace('${tabs_style}', tabs_style)
        .replace('${breadcrumbs_style}', breadcrumbs_style)
        .replace('${breadcrumbs_script}', breadcrumbs_script)
        .replace('${breadcrumbs}', breadcrumbs)
        .replace('${app_style}', app_style)
        .replace('${app_script}', app_script)
        .replace('${date}', today_string())
        .replace('${domain_name}', domain['name'])
        .replace('${domain_description}', domain['description'])
        .replace('${model}', json_for_script(model))
        .replace('${catalog}', json_for_script(catalog))
    )

    with open(os.path.join(docs_folder, 'index.html'), 'w') as html_file:
        html_file.write(rendered)

    print(domain['name'] + ': ' + str(len(model.get('stressors', []))) + ' residuality stressors')


def main():
    enter_docs_root()
    domain, _ = load_domain_args()
    create_docs(domain)


if __name__ == '__main__':
    main()
