import json
import os
import shutil
import datetime
from functools import partial

from domain_cli import load_domain_args
from generator_common import (
    domain_docs_path,
    domain_source_path,
    build_customers_lookup as build_customers_and_kpi_lookup,
    copy_icons as copy_icons_common,
    enter_docs_root,
    render_breadcrumbs as render_breadcrumbs_from,
    today_string,
)

from generator_common import template_path
from product_bricks_support import flatten_product_streams, load_product_streams_payload

domain, site_config = load_domain_args()
enter_docs_root()

date_string = today_string()

templates_root = template_path('product-deployments')
common_style = open(templates_root + '../_imports/common/style.html').read()
tabs_style = open(templates_root + '../_imports/tabs/style.html').read()
tokens_style = open(templates_root + '../_imports/tokens/style.html').read()
tabs_script = open(templates_root + '../_imports/tabs/script.html').read()
breadcrumbs_style = open(templates_root + '../_imports/breadcrumbs/style.html').read()
breadcrumbs_script = open(templates_root + '../_imports/breadcrumbs/script.html').read()

copy_icons = partial(copy_icons_common, recursive=True)


def render_breadcrumbs(template_name, replacements):
    return render_breadcrumbs_from(templates_root, template_name, replacements)


def build_customers_lookup(customers):
    lookup, _ = build_customers_and_kpi_lookup(customers)
    return lookup


def enrich_products_with_customers(products, customers_lookup):
    enriched = json.loads(json.dumps(products))
    for product in enriched.get('portfolio', {}).get('products', []):
        primary_customers = []
        for customer in product.get('primaryCustomers', []):
            customer_id = customer.get('id', '')
            info = customers_lookup.get(customer_id, {})
            primary_customers.append({
                'id': customer_id,
                'name': customer.get('name', info.get('name', customer_id)),
                'icon': info.get('icon', 'customer.png')
            })
        product['primaryCustomers'] = primary_customers
    return enriched



def load_brick_names(domain_id):
    """brick id -> display name, resolved from the brick catalog (the source
    of truth) so deployment.json does not need to duplicate brick names."""
    path = domain_source_path(domain_id, 'product-bricks/product-bricks.json')
    if not os.path.exists(path):
        return {}
    payload = json.load(open(path))
    names = {}

    def walk(node):
        if isinstance(node, dict):
            for brick in node.get('bricks', []) or []:
                if isinstance(brick, dict) and brick.get('id'):
                    names[brick['id']] = brick.get('name', brick['id'])
            for key in ('rootGroups', 'subGroups'):
                for child in node.get(key, []) or []:
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(payload.get('rootGroups', payload))
    return names


def load_deployment(domain_id):
    """Load deployment.json and enrich deployedBricks with brickName from the
    brick catalog (brickName is derived, not stored)."""
    path = domain_source_path(domain_id, 'product-deployments/deployment.json')
    deployment = json.load(open(path)) if os.path.exists(path) else {'metadata': {}, 'channels': []}
    brick_names = load_brick_names(domain_id)
    for group in deployment.get('channels', []) or []:
        for channel in group.get('channels', []) or []:
            enriched_bricks = []
            for deployed in channel.get('deployedBricks', []) or []:
                if not isinstance(deployed, dict):
                    enriched_bricks.append(deployed)
                    continue
                enriched = {'brickId': deployed.get('brickId', '')}
                enriched['brickName'] = brick_names.get(enriched['brickId'], deployed.get('brickName', enriched['brickId']))
                for key, value in deployed.items():
                    if key not in ('brickId', 'brickName'):
                        enriched[key] = value
                enriched_bricks.append(enriched)
            if 'deployedBricks' in channel:
                channel['deployedBricks'] = enriched_bricks
    return deployment


def create_overview_docs(domain, docs_folder):
    # Parse inputs before wiping the output folder, so a config error leaves
    # the previously generated docs intact.
    template = open(templates_root + 'index.html').read()
    deployment = load_deployment(domain['id'])

    if os.path.exists(docs_folder): shutil.rmtree(docs_folder)
    os.makedirs(os.path.join(docs_folder, 'icons'), exist_ok=True)

    copy_icons(templates_root + 'icons', docs_folder)
    copy_icons(domain_source_path(domain['id'], 'product-deployments/icons'), docs_folder)
    overview_image, overview_alt = copy_deployment_overview_image(domain['id'], docs_folder)

    with open(os.path.join(docs_folder, 'index.html'), 'w') as html_file:
        html_file.write(template
                        .replace('${tabs_style}', tabs_style)
                        .replace('${tokens_style}', tokens_style)
                        .replace('${tabs_script}', tabs_script)
                        .replace('${breadcrumbs_style}', breadcrumbs_style)
                        .replace('${breadcrumbs_script}', breadcrumbs_script)
                        .replace('${breadcrumbs}', render_breadcrumbs('index_breadcrumbs.json', {
                            'domain_name': domain['name']
                        }))
                        .replace('${date}', date_string)
                        .replace('${domain_name}', domain['name'])
                        .replace('${domain_description}', domain['description'])
                        .replace('${overview_image}', json.dumps(overview_image))
                        .replace('${overview_image_alt}', json.dumps(overview_alt))
                        .replace('${products}', json.dumps(products))
                        .replace('${deployment}', json.dumps(deployment)))


OVERVIEW_IMAGE_STEM = 'deployment-overview'
OVERVIEW_IMAGE_FORMATS = ('jpg', 'jpeg', 'png', 'webp')


def copy_deployment_overview_image(domain_id, docs_folder):
    """Copy the optional generated deployment map (product-deployments/media/
    deployment-overview.<fmt>) into the docs; return its docs-relative path and alt text."""
    media_dir = domain_source_path(domain_id, 'product-deployments/media')
    for fmt in OVERVIEW_IMAGE_FORMATS:
        source = os.path.join(media_dir, OVERVIEW_IMAGE_STEM + '.' + fmt)
        if os.path.isfile(source) and os.path.getsize(source):
            os.makedirs(os.path.join(docs_folder, 'media'), exist_ok=True)
            shutil.copy2(source, os.path.join(docs_folder, 'media', os.path.basename(source)))
            alt_path = os.path.join(media_dir, OVERVIEW_IMAGE_STEM + '.alt.txt')
            alt = open(alt_path, encoding='utf-8').read().strip() if os.path.isfile(alt_path) else ''
            return 'media/' + os.path.basename(source), alt
    return '', ''

def deployed_brick_ids(deployment, product_id):
    """Bricks deployed for a product on any channel, from deployment.json."""
    bricks = set()
    for group in deployment.get('channels', []):
        for channel in group.get('channels', []):
            for deployed in channel.get('deployedBricks', []):
                if any(use.get('productId') == product_id for use in deployed.get('usedInProducts', [])):
                    bricks.add(deployed.get('brickId', ''))
    bricks.discard('')
    return bricks


def build_product_context(product, deployment, streams, customers):
    """Streams, customers and jobs for one product's landing page.

    Streams are those composed of at least one brick the product deploys. A job of a
    primary customer counts as supported when one of its steps needs such a stream
    or brick, the same rule the brick pages use.
    """
    brick_ids = deployed_brick_ids(deployment, product.get('id', ''))
    product_streams = []
    for stream in streams:
        used = [dep.get('targetBrickId', '') for dep in stream.get('brickDependencies', [])
                if dep.get('targetBrickId', '') in brick_ids]
        if used:
            product_streams.append({
                'id': stream.get('id', ''), 'name': stream.get('name', ''), 'icon': stream.get('icon', ''),
                'group': stream.get('group', ''), 'description': stream.get('description', ''),
                'outcomes': stream.get('outcomes', []), 'bricksUsed': used,
            })
    stream_ids = {stream['id'] for stream in product_streams}

    customer_records = {}
    for group in customers:
        for customer in group.get('customers', []):
            customer_records[customer.get('id', '')] = dict(customer, group=group.get('group', ''))

    product_customers, jobs = [], []
    for primary in product.get('primaryCustomers', []):
        record = customer_records.get(primary.get('id', ''), {})
        product_customers.append({
            'id': primary.get('id', ''), 'name': primary.get('name', record.get('name', '')),
            'icon': primary.get('icon', record.get('icon', 'customer.png')), 'group': record.get('group', ''),
            'description': record.get('description', ''), 'careAbout': record.get('careAbout', []),
        })
        for job in record.get('jobsToBeDone', []):
            steps = []
            for step in job.get('steps', []):
                needs = [ref for ref in step.get('streamsNeeded', []) if ref.get('id') in stream_ids]
                needs += [ref for ref in step.get('bricksNeeded', []) if ref.get('id') in brick_ids]
                if needs:
                    steps.append({'step': step.get('step', ''), 'description': step.get('description', ''),
                                  'howItSupports': ' '.join(dict.fromkeys(ref.get('howItSupports', '') for ref in needs if ref.get('howItSupports')))})
            if steps:
                jobs.append({'customerId': primary.get('id', ''), 'customerName': product_customers[-1]['name'],
                             'customerIcon': product_customers[-1]['icon'], 'jobId': job.get('id', ''),
                             'jobName': job.get('name', ''), 'jobOutcome': job.get('outcome', job.get('whatItIs', '')),
                             'steps': steps})
    return product_streams, product_customers, jobs


def create_landing_pages(products, docs_folder):
    os.makedirs(os.path.join(docs_folder, 'landing_pages'), exist_ok=True)

    template = open(templates_root + 'landing_page.html').read()

    deployment = load_deployment(domain['id'])
    streams_path = domain_source_path(domain['id'], 'product-bricks/product-stream.json')
    streams = flatten_product_streams(load_product_streams_payload(streams_path))

    date_string = datetime.date.today().strftime('%Y-%m-%d')

    if 'portfolio' in products:
        for product in products['portfolio']['products']:
            product_streams, product_customers, product_jobs = build_product_context(product, deployment, streams, customers)
            landing_page_file = docs_folder + '/landing_pages/' + str(product['id']) + '.html'
            with open(landing_page_file, 'w') as html_file:
                html_file.write(template
                                .replace('${common_style}', common_style)
                                .replace('${tabs_style}', tabs_style)
                        .replace('${tokens_style}', tokens_style)
                                .replace('${tabs_script}', tabs_script)
                                .replace('${breadcrumbs_style}', breadcrumbs_style)
                                .replace('${breadcrumbs_script}', breadcrumbs_script)
                                .replace('${breadcrumbs}', render_breadcrumbs('landing_page_breadcrumbs.json', {
                                    'domain_name': domain['name'],
                                    'product_name': product['name']
                                }))
                                .replace('${date}', date_string)
                                .replace('${config}', json.dumps(site_config))
                                .replace('${all_products}', json.dumps(products['portfolio']['products']))
                                .replace('${deployment}', json.dumps(deployment))
                                .replace('${product_name}', product['name'])
                                .replace('${domain_name}', domain['name'])
                                .replace('${product_streams}', json.dumps(product_streams))
                                .replace('${product_customers}', json.dumps(product_customers))
                                .replace('${product_jobs}', json.dumps(product_jobs))
                                .replace('${product}', json.dumps(product)))


def create_deployment_landing_pages(domain, products, docs_folder):
    deployment = load_deployment(domain['id'])

    target_folder = os.path.join(docs_folder, 'deployment')
    os.makedirs(target_folder, exist_ok=True)

    template = open(templates_root + 'deployment_landing_page.html').read()

    for group in deployment.get('channels', []):
        group_id = group.get('groupId', '')
        for channel in group.get('channels', []):
            channel_id = channel.get('subChannelId', '')
            if not group_id or not channel_id:
                continue

            channel_ref = group_id + '/' + channel_id
            landing_page_file = os.path.join(target_folder, channel_id + '.html')
            with open(landing_page_file, 'w') as html_file:
                html_file.write(template
                                .replace('${common_style}', common_style)
                                .replace('${tabs_style}', tabs_style)
                        .replace('${tokens_style}', tokens_style)
                                .replace('${tabs_script}', tabs_script)
                                .replace('${breadcrumbs_style}', breadcrumbs_style)
                                .replace('${breadcrumbs_script}', breadcrumbs_script)
                                .replace('${breadcrumbs}', render_breadcrumbs('deployment_landing_page_breadcrumbs.json', {
                                    'domain_name': domain['name'],
                                    'channel_name': channel.get('subChannelName', channel.get('name', channel_id))
                                }))
                                .replace('${date}', date_string)
                                .replace('${domain_name}', domain['name'])
                                .replace('${sub_channel_name}', channel.get('subChannelName', channel.get('name', channel_id)))
                                .replace('${domain_description}', domain['description'])
                                .replace('${products}', json.dumps(products))
                                .replace('${deployment}', json.dumps(deployment))
                                .replace('${channel_ref}', json.dumps(channel_ref)))

domain_id = domain['id']
products_file_path = domain_source_path(domain_id, 'product-deployments/products.json')
print(products_file_path)
if not os.path.exists(products_file_path):
    raise SystemExit(f"Missing products config for domain '{domain_id}'")

customers_path = domain_source_path(domain_id, 'customers/customers.json')
if not os.path.exists(customers_path):
    customers_path = domain_source_path(domain_id, 'product/customers.json')

customers = json.load(open(customers_path)) if os.path.exists(customers_path) else []
customers_lookup = build_customers_lookup(customers)

products = enrich_products_with_customers(json.load(open(products_file_path)), customers_lookup)

docs_folder = domain_docs_path(domain_id, 'product-deployments') + '/'
create_overview_docs(domain, docs_folder)
create_landing_pages(products, docs_folder)
create_deployment_landing_pages(domain, products, docs_folder)
