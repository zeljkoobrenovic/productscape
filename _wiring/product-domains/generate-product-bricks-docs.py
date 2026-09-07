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
    today_string,
)
from product_bricks_support import (
    flatten_product_bricks,
    flatten_product_streams,
    load_data_assets_payload,
    load_product_bricks_payload,
    load_product_streams_payload,
    sanitize_product_stream_root_groups,
)

from generator_common import template_path

enter_docs_root()

date_string = today_string()

root_templates = template_path('product-bricks')
domain, site_config = load_domain_args()

common_style = open(root_templates + '../_imports/common/style.html').read()

breadcrumbs_style = open(root_templates + '../_imports/breadcrumbs/style.html').read()
breadcrumbs_script = open(root_templates + '../_imports/breadcrumbs/script.html').read()

tabs_style = open(root_templates + '../_imports/tabs/style.html').read()
tokens_style = open(root_templates + '../_imports/tokens/style.html').read()
tabs_script = open(root_templates + '../_imports/tabs/script.html').read()


def build_customer_lookup(customers):
    lookup = {}
    for group in customers:
        group_name = group.get('group', '')
        for customer in group.get('customers', []):
            enriched = dict(customer)
            enriched['group'] = group_name
            lookup[customer['id']] = enriched
    return lookup


def build_brick_context(brick, products, customers, deployment_payload=None, streams=None, required_stream_id=None):
    customer_lookup = build_customer_lookup(customers)
    linked_products = []
    supported_jobs = []
    supported_jobs_index = {}

    brick_id = str(brick.get('id', '')).strip().lower()
    brick_name = str(brick.get('name', '')).strip().lower()
    composing_stream_ids = {
        str(stream.get('id', '')).strip().lower()
        for stream in streams or []
        if any(str(dep.get('targetBrickId', '')).strip().lower() == brick_id
               for dep in stream.get('brickDependencies', []))
    }
    deployed_products = {}

    def collect_deployments(channels):
        for channel in channels or []:
            for deployed in channel.get('deployedBricks', []):
                if str(deployed.get('brickId', '')).strip().lower() != brick_id:
                    continue
                for usage in deployed.get('usedInProducts', []):
                    product_id = str(usage.get('productId', '')).strip()
                    if product_id:
                        reasons = deployed_products.setdefault(product_id, [])
                        reason = usage.get('description') or deployed.get('deploymentRole', '')
                        if reason and reason not in reasons:
                            reasons.append(reason)
            collect_deployments(channel.get('channels', []))

    collect_deployments((deployment_payload or {}).get('channels', []))

    def stream_matches(stream):
        stream_code = str(stream.get('id', stream.get('streamCode', ''))).strip().lower()
        stream_name = str(stream.get('name', stream.get('streamName', ''))).strip().lower()
        return stream_code == brick_id or stream_name == brick_name or stream_code in composing_stream_ids

    def append_supported_job(customer, primary_customer, product, job, step, stream, matched_stream):
        item_key = (
            customer.get('id', primary_customer.get('id', '')),
            product.get('id', ''),
            job.get('id', ''),
        )
        if item_key not in supported_jobs_index:
            supported_jobs_index[item_key] = {
                'customerId': customer.get('id', primary_customer.get('id', '')),
                'customerName': customer.get('name', primary_customer.get('name', '')),
                'customerGroup': customer.get('group', ''),
                'customerIcon': customer.get('icon', 'customer.png'),
                'productId': product.get('id', ''),
                'productName': product.get('name', ''),
                'productIcon': product.get('icon', 'product.png'),
                'jobId': job.get('id', ''),
                'jobName': job.get('name', ''),
                'jobWhatItIs': job.get('whatItIs', ''),
                'jobOutcome': job.get('outcome', ''),
                'supportRationale': stream.get('howItSupports', '') or matched_stream.get('whyNeeded', ''),
                'usedInSteps': []
            }
            supported_jobs.append(supported_jobs_index[item_key])

        supported_job = supported_jobs_index[item_key]
        used_step = {
            'step': step.get('step', ''),
            'description': step.get('description', ''),
            'howItSupports': stream.get('howItSupports', '') or matched_stream.get('whyNeeded', ''),
            'media': step.get('media', [])
        }
        if used_step not in supported_job['usedInSteps']:
            supported_job['usedInSteps'].append(used_step)

    for product in products.get('portfolio', {}).get('products', []):
        matched_stream = None
        for stream in product.get('neededStreams', []):
            if stream_matches(stream):
                matched_stream = stream
                break

        # Current portfolios connect products to bricks through deployment.json.
        # Keep the legacy neededStreams path for older domain source packages.
        product_id = str(product.get('id', '')).strip()
        if product_id in deployed_products:
            matched_stream = {'whyNeeded': ' '.join(deployed_products[product_id])}

        if matched_stream is None:
            continue

        previous_job_count = len(supported_jobs)
        for primary_customer in product.get('primaryCustomers', []):
            customer = customer_lookup.get(primary_customer.get('id', ''), {})
            for job in customer.get('jobsToBeDone', []):
                for step in job.get('steps', []):
                    if required_stream_id and not any(
                        str(ref.get('id', ref.get('streamCode', ''))).strip() == required_stream_id
                        for ref in step.get('streamsNeeded', [])
                    ):
                        continue
                    # streamsNeeded references product streams; bricksNeeded carries the
                    # lower-level brick implementation dependencies. Match against both so a
                    # brick page surfaces the jobs it supports directly or via a stream.
                    for stream in step.get('streamsNeeded', []) + step.get('bricksNeeded', []):
                        if stream_matches(stream):
                            append_supported_job(customer, primary_customer, product, job, step, stream, matched_stream)

        # A shared foundation alone does not imply that every consuming product
        # supports every stream. Stream pages require a matching customer step.
        if required_stream_id and len(supported_jobs) == previous_job_count:
            continue
        linked_products.append({
            'id': product.get('id', ''),
            'name': product.get('name', ''),
            'icon': product.get('icon', 'product.png'),
            'type': product.get('type', ''),
            'whyUsed': matched_stream.get('whyNeeded', '')
        })

    return linked_products, supported_jobs


def _iter_team_groups(groups):
    """Yield (group, team) for every team in the recursive group tree."""
    for group in groups or []:
        for team in group.get('teams', []):
            yield group, team
        for descendant in _iter_team_groups(group.get('groups', [])):
            yield descendant


def build_brick_team_context(brick, teams_payload):
    related_teams = []
    brick_id = str(brick.get('id', '')).strip()

    for group, team in _iter_team_groups(teams_payload.get('groups', [])):
        links = team.get('brickDependencies', [])
        if not any(str(link.get('brickId', '')).strip() == brick_id for link in links):
            continue

        related_teams.append({
            'teamId': team.get('id', ''),
            'teamName': team.get('name', team.get('id', '')),
            'teamType': team.get('type', ''),
            'groupId': group.get('id', ''),
            'groupName': group.get('name', ''),
            'role': 'related',
            'roleLabel': 'Related team'
        })

    related_teams.sort(key=lambda item: item['teamName'].lower())
    return related_teams


def build_team_lookup(teams_payload):
    """Map teamId -> {teamId, teamName, groupName, teamType} for ownership resolution."""
    lookup = {}
    for group, team in _iter_team_groups(teams_payload.get('groups', [])):
        team_id = str(team.get('id', '')).strip()
        if not team_id:
            continue
        lookup[team_id] = {
            'teamId': team_id,
            'teamName': team.get('name', team_id),
            'teamType': team.get('type', ''),
            'groupName': group.get('name', ''),
        }
    return lookup


def flatten_data_assets_with_context(root_groups):
    """Flatten the recursive data-asset group tree, annotating each asset with its
    rootGroup / group names so landing pages can show the catalog path."""
    flat = []

    def walk(groups, root_name, parent_name):
        for group in groups or []:
            group_name = group.get('name', '')
            current_root = root_name or group_name
            for asset in group.get('assets', []):
                annotated = dict(asset)
                annotated['rootGroup'] = current_root
                annotated['group'] = group_name
                flat.append(annotated)
            walk(group.get('subGroups', []), current_root, group_name)

    walk(root_groups, '', '')
    return flat


def build_data_asset_brick_usage(asset_id, bricks):
    """Mirror the index page's buildDataAssetUsage: split linking bricks into
    producing (own/write/publish/replicate/delete) and consuming (read/query/...)."""
    producing = []
    consuming = []
    producing_roles = {'own', 'write', 'publish', 'replicate', 'delete'}
    for brick in bricks:
        for dep in brick.get('dataDependencies', []):
            if dep.get('assetId') != asset_id:
                continue
            entry = {
                'id': brick.get('id', ''),
                'name': brick.get('name', brick.get('id', '')),
                'role': dep.get('role', ''),
                'description': dep.get('description', ''),
            }
            if str(dep.get('role', '')).lower() in producing_roles:
                producing.append(entry)
            else:
                consuming.append(entry)
    return producing, consuming



def dedupe_by(items, key_builder):
    index = {}
    ordered = []
    for item in items:
        key = key_builder(item)
        if key in index:
            continue
        index[key] = True
        ordered.append(item)
    return ordered


def merge_supported_jobs(items):
    merged = {}
    ordered = []

    for item in items:
        key = (
            item.get('customerId', ''),
            item.get('productId', ''),
            item.get('jobId', '')
        )
        if key not in merged:
            merged[key] = dict(item)
            merged[key]['usedInSteps'] = list(item.get('usedInSteps', []))
            ordered.append(merged[key])
            continue

        existing = merged[key]
        if not existing.get('supportRationale') and item.get('supportRationale'):
            existing['supportRationale'] = item.get('supportRationale')

        existing_steps = existing.setdefault('usedInSteps', [])
        for step in item.get('usedInSteps', []):
            if step not in existing_steps:
                existing_steps.append(step)

    return ordered


def merge_named_records(items, id_field, list_fields=None):
    merged = {}
    ordered = []
    list_fields = list_fields or []

    for item in items:
        item_id = item.get(id_field, '')
        if item_id not in merged:
            merged[item_id] = dict(item)
            for field in list_fields:
                merged[item_id][field] = list(item.get(field, []))
            ordered.append(merged[item_id])
            continue

        existing = merged[item_id]
        for field, value in item.items():
            if field in list_fields:
                continue
            if not existing.get(field) and value:
                existing[field] = value

        for field in list_fields:
            existing_values = existing.setdefault(field, [])
            for value in item.get(field, []):
                if value not in existing_values:
                    existing_values.append(value)

    return ordered


def create_landing_pages(bricks, products, customers, teams_payload, deployment_payload=None, streams=None):
    landing_page_template = open(root_templates + 'brick_landing_page.html').read();
    breadcrumbs = open(root_templates + 'brick_landing_page_breadcrumbs.json').read();

    for brick in bricks:
        name = brick['name']
        linked_products, supported_jobs = build_brick_context(brick, products, customers, deployment_payload, streams)
        related_teams = build_brick_team_context(brick, teams_payload)

        htmlFile = docs_folder + 'landing_pages/' + str(brick['id']) + '.html'
        with open(htmlFile, 'w') as html_file:
            html_file.write(landing_page_template
                            .replace('${tabs_style}', tabs_style)
                        .replace('${tokens_style}', tokens_style)
                            .replace('${tabs_script}', tabs_script)
                            .replace('${date}', date_string)
                            .replace('${config}', json.dumps(site_config))
                            .replace('${brick_data}', json.dumps(brick))
                            .replace('${common_style}', common_style)
                            .replace('${breadcrumbs_style}', breadcrumbs_style)
                            .replace('${breadcrumbs_script}', breadcrumbs_script)
                            .replace('${breadcrumbs}', breadcrumbs)
                            .replace('${domain_name}', domain['name'])
                            .replace('${brick_name}', name.replace('&', '&amp;'))
                            .replace('${related_teams}', json.dumps(related_teams))
                            .replace('${linked_products}', json.dumps(linked_products))
                            .replace('${supported_jobs}', json.dumps(supported_jobs)))


def create_stream_landing_pages(streams, bricks, products, customers, teams_payload, deployment_payload=None):
    landing_page_template = open(root_templates + 'stream_landing_page.html').read();
    brick_lookup = {brick['id']: brick for brick in bricks}
    breadcrumbs = open(root_templates + 'stream_landing_page_breadcrumbs.json').read();

    for stream in streams:
        related_bricks = []
        linked_products = list(stream.get('supportedProducts', []))
        supported_jobs = list(stream.get('supportedCustomerJobs', []))
        related_teams = list(stream.get('owningTeams', []))

        for dep in stream.get('brickDependencies', []):
            brick_id = dep.get('targetBrickId', dep.get('targetobjectId', ''))
            if not brick_id or brick_id not in brick_lookup:
                continue
            brick = brick_lookup[brick_id]
            related_bricks.append(brick)
            brick_linked_products, brick_supported_jobs = build_brick_context(
                brick, products, customers, deployment_payload, streams, required_stream_id=stream.get('id')
            )
            linked_products.extend(brick_linked_products)
            supported_jobs.extend(brick_supported_jobs)
            related_teams.extend(build_brick_team_context(brick, teams_payload))

        related_bricks = dedupe_by(related_bricks, lambda item: item.get('id', ''))
        linked_products = merge_named_records(linked_products, 'id')
        supported_jobs = merge_supported_jobs(supported_jobs)
        related_teams = merge_named_records(related_teams, 'teamId')
        html_file = docs_folder + 'stream_pages/' + str(stream['id']) + '.html'
        with open(html_file, 'w') as html_file:
            html_file.write(landing_page_template
                            .replace('${tabs_style}', tabs_style)
                        .replace('${tokens_style}', tokens_style)
                            .replace('${tabs_script}', tabs_script)
                            .replace('${config}', json.dumps(site_config))
                            .replace('${stream_data}', json.dumps(stream))
                            .replace('${related_bricks}', json.dumps(related_bricks))
                            .replace('${common_style}', common_style)
                            .replace('${breadcrumbs_style}', breadcrumbs_style)
                            .replace('${breadcrumbs_script}', breadcrumbs_script)
                            .replace('${breadcrumbs}', breadcrumbs)
                            .replace('${domain_name}', domain['name'])
                            .replace('${breadcrumbs_style}', breadcrumbs_style)
                            .replace('${breadcrumbs_script}', breadcrumbs_script)
                            .replace('${stream_name}', stream.get('name', stream.get('id', '')).replace('&', '&amp;'))
                            .replace('${linked_products}', json.dumps(linked_products))
                            .replace('${related_teams}', json.dumps(related_teams))
                            .replace('${supported_jobs}', json.dumps(supported_jobs)))


def create_data_asset_landing_pages(data_assets_payload, bricks, teams_payload):
    template_path = root_templates + 'data_asset_landing_page.html'
    breadcrumbs_path = root_templates + 'data_asset_landing_page_breadcrumbs.json'
    if not os.path.exists(template_path):
        return

    landing_page_template = open(template_path).read()
    breadcrumbs = open(breadcrumbs_path).read()

    assets = flatten_data_assets_with_context(data_assets_payload.get('rootGroups', []))
    stores = data_assets_payload.get('stores', [])
    team_lookup = build_team_lookup(teams_payload)

    # Lightweight catalog for the nav strip on each page (no need to inline everything).
    nav_assets = [{'id': asset.get('id', ''), 'name': asset.get('name', asset.get('id', ''))} for asset in assets]

    for asset in assets:
        asset_id = str(asset.get('id', '')).strip()
        if not asset_id:
            continue

        producing_bricks, consuming_bricks = build_data_asset_brick_usage(asset_id, bricks)
        owner_team = team_lookup.get(str(asset.get('ownerTeamId', '')).strip()) if asset.get('ownerTeamId') else None
        steward_teams = [
            team_lookup[steward_id]
            for steward_id in asset.get('stewardTeamIds', [])
            if str(steward_id).strip() in team_lookup
        ]

        html_path = docs_folder + 'data_pages/' + asset_id + '.html'
        with open(html_path, 'w') as html_file:
            html_file.write(landing_page_template
                            .replace('${tabs_style}', tabs_style)
                        .replace('${tokens_style}', tokens_style)
                            .replace('${tabs_script}', tabs_script)
                            .replace('${config}', json.dumps(site_config))
                            .replace('${asset_data}', json.dumps(asset))
                            .replace('${producing_bricks}', json.dumps(producing_bricks))
                            .replace('${consuming_bricks}', json.dumps(consuming_bricks))
                            .replace('${owner_team}', json.dumps(owner_team))
                            .replace('${steward_teams}', json.dumps(steward_teams))
                            .replace('${common_style}', common_style)
                            .replace('${breadcrumbs_style}', breadcrumbs_style)
                            .replace('${breadcrumbs_script}', breadcrumbs_script)
                            .replace('${breadcrumbs}', breadcrumbs)
                            .replace('${domain_name}', domain['name'])
                            .replace('${asset_name}', (asset.get('name', asset_id)).replace('&', '&amp;')))


domain_id = domain['id']
docs_folder = domain_docs_path(domain_id, 'product-bricks') + '/'
root_domain = domain_source_path(domain_id, 'product-bricks') + '/'
product_bricks_config_path = root_domain + 'product-bricks.json'
product_streams_config_path = root_domain + 'product-stream.json'
data_assets_config_path = domain_source_path(domain_id, 'data/data-assets.json')

if not os.path.exists(product_bricks_config_path):
    raise SystemExit(f"Missing product bricks config for domain '{domain_id}'")

print(root_domain)

# Parse every input BEFORE wiping the output folder, so a config error
# leaves the previously generated docs intact instead of destroying them.
data = load_product_bricks_payload(product_bricks_config_path)
flat_bricks = flatten_product_bricks(data)
streams_payload = load_product_streams_payload(product_streams_config_path)
flat_streams = flatten_product_streams(streams_payload)
data_assets_payload = load_data_assets_payload(data_assets_config_path)
products = load_json_if_exists(domain_source_path(domain_id, 'product-deployments/products.json'), {'portfolio': {'products': []}})
deployment_payload = load_json_if_exists(domain_source_path(domain_id, 'product-deployments/deployment.json'), {'channels': []})
customers = load_json_if_exists(domain_source_path(domain_id, 'customers/customers.json'), [])
teams_payload = load_json_if_exists(domain_source_path(domain_id, 'teams/teams.json'), {'groups': []})

if os.path.exists(docs_folder): shutil.rmtree(docs_folder)
os.makedirs(os.path.join(docs_folder, 'icons'), exist_ok=True)
os.makedirs(os.path.join(docs_folder, 'landing_pages'), exist_ok=True)
os.makedirs(os.path.join(docs_folder, 'stream_pages'), exist_ok=True)
os.makedirs(os.path.join(docs_folder, 'data_pages'), exist_ok=True)

copy_icons(root_templates + 'icons', docs_folder)
copy_icons(domain_source_path(domain_id, 'product-bricks/icons'), docs_folder)

with open(docs_folder + 'index.html', 'w') as html_file:
    template = open(root_templates + 'index.html').read()

    breadcrumbs = open(root_templates + 'index_breadcrumbs.json').read();

    content = template.replace('${domain_description}', domain['description'])
    content = content.replace('${bricks}', json.dumps(data)) \
        .replace('${data_assets}', json.dumps(data_assets_payload)) \
        .replace('${tabs_style}', tabs_style) \
        .replace('${tokens_style}', tokens_style) \
        .replace('${tabs_script}', tabs_script) \
        .replace('${breadcrumbs_style}', breadcrumbs_style) \
        .replace('${breadcrumbs_script}', breadcrumbs_script) \
        .replace('${breadcrumbs}', breadcrumbs) \
        .replace('${domain_name}', domain['name'])

    content = content.replace('${product_streams}', json.dumps({
        'metadata': streams_payload.get('metadata', {}),
        'rootGroups': sanitize_product_stream_root_groups(streams_payload.get('rootGroups', [])),
        'experiences': flat_streams,
        'streams': flat_streams
    }))
    html_file.write(content)


# The landing pages under landing_pages/, stream_pages/, and data_pages/ all
# load ../shared_data.js instead of inlining these payloads per page — one
# copy per domain instead of one per page (works from file:// too, unlike fetch).
_shared_assets = flatten_data_assets_with_context(data_assets_payload.get('rootGroups', []))
shared_domain_data = {
    'allBricks': flat_bricks,
    'allStreams': flat_streams,
    'bricksMetadata': data.get('metadata', {}),
    'dataAssetsPayload': data_assets_payload,
    'allAssets': [{'id': a.get('id', ''), 'name': a.get('name', a.get('id', ''))} for a in _shared_assets],
    'allStores': data_assets_payload.get('stores', []),
}
with open(docs_folder + 'shared_data.js', 'w') as shared_file:
    shared_file.write('window.SHARED_DOMAIN_DATA = ' + json.dumps(shared_domain_data, ensure_ascii=False) + ';\n')

create_landing_pages(flat_bricks, products, customers, teams_payload, deployment_payload, flat_streams)
create_stream_landing_pages(flat_streams, flat_bricks, products, customers, teams_payload, deployment_payload)
create_data_asset_landing_pages(data_assets_payload, flat_bricks, teams_payload)
