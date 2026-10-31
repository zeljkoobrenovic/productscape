import json
import os
import shutil

from domain_cli import load_domain_args
from generator_common import (
    domain_docs_path,
    domain_source_path,
    copy_icons,
    enter_docs_root,
    load_json_if_exists,
    normalize_icon_name,
    today_string,
)
from product_bricks_support import (
    flatten_product_bricks,
    flatten_product_streams,
    load_data_assets_payload,
    load_product_bricks_payload,
    load_product_streams_payload,
)

from generator_common import template_path

domain, _ = load_domain_args()
enter_docs_root()

date_string = today_string()

from generator_common import navigation_path
apps = json.load(open(navigation_path()))

templates_root = template_path('start')

tabs_style = open(templates_root + '../_imports/tabs/style.html').read()
tokens_style = open(templates_root + '../_imports/tokens/style.html').read()
tabs_script = open(templates_root + '../_imports/tabs/script.html').read()


def group_items(entries):
    """Group (group_name, item) pairs, keeping first-seen group order."""
    groups = {}
    for group_name, item in entries:
        groups.setdefault(group_name or 'Other', []).append(item)
    return [{'name': name, 'items': items} for name, items in groups.items()]


def sidebar_item(name, link, icon, fallback, description=''):
    return {
        'name': name or '',
        'link': link,
        'icon': icon,
        'fallback': fallback,
        'description': ' '.join(str(description or '').split())[:160],
    }


def view(name, link, icon, count=None):
    # A tab of a section's overview page, listed in the sidebar as a page of its own.
    # A count shows on the start page's card that links to the same tab.
    entry = {'name': name, 'link': link, 'icon': icon, 'fallback': icon}
    if count is not None:
        entry['count'] = count
    return entry


def customers_section(domain_id):
    customers = load_json_if_exists(domain_source_path(domain_id, 'customers/customers.json'), [])
    insights = load_json_if_exists(domain_source_path(domain_id, 'customers/insights.json'), {})
    entries = []
    for group in customers:
        for customer in group.get('customers', []):
            if not customer.get('id'):
                continue
            entries.append((group.get('group', ''), sidebar_item(
                customer.get('name'), '../customers/landing_pages/' + str(customer['id']) + '.html',
                '../customers/icons/' + normalize_icon_name(customer.get('icon')), '../customers/icons/customer.png',
                customer.get('description'))))
    return {'id': 'customers', 'title': 'Customers', 'link': '../customers/index.html',
            'icon': '../customers/icons/logo.png', 'groups': group_items(entries), 'views': [
                view('Visual Overview', '../customers/index.html#visual-overview', '../customers/icons/customer.png'),
                view('Relations', '../customers/index.html#relations', '../customers/icons/care.png'),
                view('Insights', '../customers/index.html#insights', '../customers/icons/insights.png',
                     len(insights.get('items', []))),
                view('Links', '../customers/index.html#links', '../customers/icons/link.png'),
            ]}


def bricks_sections(domain_id):
    bricks_path = domain_source_path(domain_id, 'product-bricks/product-bricks.json')
    streams_path = domain_source_path(domain_id, 'product-bricks/product-stream.json')
    bricks = flatten_product_bricks(load_product_bricks_payload(bricks_path))
    streams = flatten_product_streams(load_product_streams_payload(streams_path))
    data_assets = load_data_assets_payload(domain_source_path(domain_id, 'data/data-assets.json'))

    brick_entries = [(brick.get('domain'), sidebar_item(
        brick.get('name'), '../product-bricks/landing_pages/' + str(brick['id']) + '.html',
        '../product-bricks/icons/' + str(brick['id']) + '.png', '../product-bricks/icons/brick.png',
        brick.get('description'))) for brick in bricks if brick.get('id')]
    stream_entries = [(stream.get('rootGroup'), sidebar_item(
        stream.get('name'), '../product-bricks/stream_pages/' + str(stream['id']) + '.html',
        '../product-bricks/icons/' + str(stream.get('icon') or 'stream.png'), '../product-bricks/icons/stream.png',
        stream.get('description'))) for stream in streams if stream.get('id')]

    # Mirrors flatten_data_assets_with_context in generate-product-bricks-docs.py,
    # which decides which data_pages/ exist.
    asset_entries = []

    def walk_assets(groups, root_name):
        for group in groups or []:
            current_root = root_name or group.get('name', '')
            for asset in group.get('assets', []):
                asset_id = str(asset.get('id', '')).strip()
                if asset_id:
                    asset_entries.append((current_root, sidebar_item(
                        asset.get('name', asset_id), '../product-bricks/data_pages/' + asset_id + '.html',
                        '../product-bricks/icons/data-asset.png', '../product-bricks/icons/data.png',
                        asset.get('description'))))
            walk_assets(group.get('subGroups', []), current_root)

    walk_assets(data_assets.get('rootGroups', []), '')

    return [
        {'id': 'bricks', 'title': 'Product Bricks', 'link': '../product-bricks/index.html',
         'icon': '../product-bricks/icons/logo.png', 'groups': group_items(brick_entries), 'views': [
             view('Dependencies', '../product-bricks/index.html#dependencies', '../product-bricks/icons/integration.png'),
         ]},
        {'id': 'streams', 'title': 'Streams', 'link': '../product-bricks/index.html#streams',
         'icon': '../product-bricks/icons/stream.png', 'groups': group_items(stream_entries)},
        {'id': 'data', 'title': 'Data Assets', 'link': '../product-bricks/index.html#data',
         'icon': '../product-bricks/icons/data-asset.png', 'groups': group_items(asset_entries)},
    ]


def products_sections(domain_id):
    products = load_json_if_exists(domain_source_path(domain_id, 'product-deployments/products.json'), {})
    deployment = load_json_if_exists(domain_source_path(domain_id, 'product-deployments/deployment.json'), {})
    product_entries = [(product.get('type'), sidebar_item(
        product.get('name'), '../product-deployments/landing_pages/' + str(product['id']) + '.html',
        '../product-deployments/icons/' + (product.get('icon') or 'product.png'), '../product-deployments/icons/product.png',
        product.get('description'))) for product in products.get('portfolio', {}).get('products', []) if product.get('id')]
    deployment_entries = []
    for group in deployment.get('channels', []) or []:
        for channel in group.get('channels', []) or []:
            channel_id = channel.get('subChannelId', '')
            if group.get('groupId') and channel_id:
                deployment_entries.append((group.get('groupName', group.get('groupId')), sidebar_item(
                    channel.get('subChannelName', channel.get('name', channel_id)),
                    '../product-deployments/deployment/' + channel_id + '.html',
                    '../product-deployments/icons/deployment/deployment.png', '../product-deployments/icons/logo.png',
                    channel.get('description'))))
    return [
        {'id': 'products', 'title': 'Products', 'link': '../product-deployments/index.html',
         'icon': '../product-deployments/icons/logo.png', 'groups': group_items(product_entries), 'views': [
             view('Dependencies', '../product-deployments/index.html#dependencies', '../product-bricks/icons/integration.png'),
             view('Matrix', '../product-deployments/index.html#matrix', '../product-deployments/icons/dashboard.png'),
         ]},
        # The overview card links to the Products tab but also counts the deployments.
        {'id': 'deployments', 'title': 'Deployments', 'link': '../product-deployments/index.html#deployment',
         'card': '../product-deployments/index.html',
         'icon': '../product-deployments/icons/deployment/deployment.png', 'groups': group_items(deployment_entries)},
    ]


def competition_section(domain_id):
    competition_path = domain_source_path(domain_id, 'business', 'competition.json')
    if not os.path.exists(competition_path):
        return None
    logos_root = domain_source_path(domain_id, 'business', 'logos')
    logos = {}
    if os.path.isdir(logos_root):
        for filename in sorted(os.listdir(logos_root)):
            logos.setdefault(filename, filename)
            logos.setdefault(os.path.splitext(filename)[0], filename)
    entries = []
    for player in json.load(open(competition_path)).get('players', []):
        if not player.get('id'):
            continue
        logo = player.get('logo')
        logo = logo.get('local_file') if isinstance(logo, dict) else logo
        candidates = [os.path.basename(logo), os.path.splitext(os.path.basename(logo))[0]] if isinstance(logo, str) and logo else []
        logo_file = next((logos[name] for name in candidates + [player['id']] if name in logos), None)
        entries.append((str(player.get('category', '')).replace('_', ' '), sidebar_item(
            player.get('name'), '../competition/landing_pages/' + str(player['id']) + '.html',
            '../competition/logos/' + logo_file if logo_file else '../competition/icons/logo.png',
            '../competition/icons/logo.png', player.get('description'))))
    return {'id': 'competition', 'title': 'Competition', 'link': '../competition/index.html',
            'icon': '../competition/icons/logo.png', 'groups': group_items(entries)}


def sidebar_sections(domain_id):
    # The sidebar shows these categories as headings above their sections.
    categories = [
        ('Business', [customers_section(domain_id), competition_section(domain_id)]),
        ('Product Architecture', [*bricks_sections(domain_id), *products_sections(domain_id)]),
    ]
    sections = [dict(section, category=category) for category, members in categories
                for section in members if section and section['groups']]
    # Single pages listed directly under "More", without a collapsible list.
    sections += [
        {'id': 'residuality', 'title': 'Stress Test', 'link': '../residuality/index.html',
         'icon': 'icons/residuality.png', 'groups': [], 'category': 'More'},
        {'id': 'tutorial', 'title': 'Domain Tutorial', 'link': '../tutorial/index.html',
         'icon': 'icons/initiative.png', 'groups': [], 'category': 'More'},
    ]
    return sections


def script_json(value):
    # Keep "</script>" inside names or descriptions from closing the inline script.
    return json.dumps(value).replace('</', '<\\/')


def create_docs(domain, docs_folder):
    source_icons = domain_source_path(domain['id'], 'start/icons')
    if os.path.exists(docs_folder): shutil.rmtree(docs_folder)
    os.makedirs(os.path.join(docs_folder, 'icons'), exist_ok=True)

    copy_icons(templates_root + 'icons', docs_folder)
    copy_icons(source_icons, docs_folder)

    with open(os.path.join(docs_folder, 'index.html'), 'w') as html_file:
        template = open(templates_root + 'index.html').read()
        print(domain['description'])
        html_file.write(template
                        .replace('${tabs_style}', tabs_style)
                        .replace('${tokens_style}', tokens_style)
                        .replace('${tabs_script}', tabs_script)
                        .replace('${date}', date_string)
                        .replace('${apps}', script_json(apps))
                        .replace('${sidebar_sections}', script_json(sidebar_sections(domain['id'])))
                        .replace('${domain_name}', domain['name'])
                        .replace('${domain_description}', domain['description']))


docs_folder = domain_docs_path(domain['id'], 'start') + '/'
create_docs(domain, docs_folder)
