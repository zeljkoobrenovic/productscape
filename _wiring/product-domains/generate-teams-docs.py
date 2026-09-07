import json
import os
import shutil

from domain_cli import load_domain_args
from generator_common import (
    domain_docs_path,
    domain_source_path,
    build_customers_lookup,
    copy_icons,
    enter_docs_root,
    load_json_if_exists,
    normalize_icon_name,
    render_breadcrumbs as render_breadcrumbs_from,
    today_string,
)
from product_bricks_support import (
    apply_shared_defaults,
    build_bricks_lookup,
    flatten_product_streams,
    load_product_bricks_payload,
    load_product_streams_payload,
)

from generator_common import template_path

enter_docs_root()

date_string = today_string()

templates_root = template_path('teams')
domain, _ = load_domain_args()

common_style = open(templates_root + '../_imports/common/style.html').read()
tabs_style = open(templates_root + '../_imports/tabs/style.html').read()
tokens_style = open(templates_root + '../_imports/tokens/style.html').read()
tabs_script = open(templates_root + '../_imports/tabs/script.html').read()
breadcrumbs_style = open(templates_root + '../_imports/breadcrumbs/style.html').read()
breadcrumbs_script = open(templates_root + '../_imports/breadcrumbs/script.html').read()


def render_breadcrumbs(template_name, replacements):
    return render_breadcrumbs_from(templates_root, template_name, replacements)


def build_streams_lookup(streams):
    lookup = {}
    for stream in streams:
        stream_id = str(stream.get('id', '')).strip()
        if not stream_id:
            continue
        lookup[stream_id] = {
            'id': stream_id,
            'name': stream.get('name', stream_id),
            'icon': normalize_icon_name(stream.get('icon', ''), stream_id + '.png'),
            'type': stream.get('type', ''),
        }
    return lookup


from generator_common import iter_group_tree as iter_groups


def build_team_lookup(teams_payload):
    lookup = {}
    for group, _ in iter_groups(teams_payload.get('groups', [])):
        for team in group.get('teams', []):
            lookup[team['id']] = {
                'id': team['id'],
                'name': team.get('name', team['id']),
                'type': team.get('type', ''),
                'groupId': group.get('id', ''),
                'groupName': group.get('name', ''),
            }
    return lookup


def enrich_team(team, group, team_lookup, customers_lookup, bricks_lookup,
                streams_lookup, dependency_type_lookup):
    enriched = dict(team)
    enriched['groupId'] = group.get('id', '')
    enriched['groupName'] = group.get('name', '')

    customer_links = []
    for dependency in team.get('customerDependencies', []) or []:
        customer_id = dependency.get('customerId', '')
        info = customers_lookup.get(customer_id, {})
        customer_links.append({
            'customerId': customer_id,
            'name': info.get('name', customer_id),
            'icon': normalize_icon_name(info.get('icon', 'customer.png')),
            'href': '../customers/landing_pages/' + customer_id + '.html',
            'description': dependency.get('description', ''),
        })
    enriched['customerDependencies'] = customer_links

    stream_links = []
    for dependency in team.get('streamDependencies', []) or []:
        stream_id = dependency.get('streamId', '')
        info = streams_lookup.get(stream_id, {})
        stream_links.append({
            'streamId': stream_id,
            'name': info.get('name', stream_id),
            'icon': normalize_icon_name(info.get('icon', ''), stream_id + '.png'),
            'href': '../product-bricks/stream_pages/' + stream_id + '.html',
            'description': dependency.get('description', ''),
        })
    enriched['streamDependencies'] = stream_links

    brick_links = []
    for dependency in team.get('brickDependencies', []) or []:
        brick_id = str(dependency.get('brickId', '')).strip()
        info = bricks_lookup.get(brick_id, {})
        brick_links.append({
            'brickId': brick_id,
            'name': info.get('name', brick_id),
            'icon': normalize_icon_name(info.get('icon', ''), brick_id + '.png'),
            'href': '../product-bricks/landing_pages/' + brick_id + '.html',
            'description': dependency.get('description', ''),
        })
    enriched['brickDependencies'] = brick_links

    team_links = []
    for dependency in team.get('otherTeamDependencies', []) or []:
        other_id = dependency.get('teamId', '')
        info = team_lookup.get(other_id, {})
        dependency_type = dependency.get('type', '')
        type_info = dependency_type_lookup.get(dependency_type, {})
        team_links.append({
            'teamId': other_id,
            'name': info.get('name', other_id),
            'type': info.get('type', ''),
            'groupName': info.get('groupName', ''),
            'href': 'landing_pages/' + other_id + '.html',
            'dependencyType': dependency_type,
            'dependencyTypeName': type_info.get('name', dependency_type),
            'description': dependency.get('description', ''),
        })
    enriched['otherTeamDependencies'] = team_links

    return enriched


def enrich_groups(groups, team_lookup, customers_lookup, bricks_lookup,
                  streams_lookup, dependency_type_lookup):
    enriched_groups = []
    for group in groups or []:
        direct = group.get('groupDirectHeadcount', {}) or {}
        teams = [
            enrich_team(team, group, team_lookup, customers_lookup, bricks_lookup,
                        streams_lookup, dependency_type_lookup)
            for team in group.get('teams', [])
        ]
        child_groups = enrich_groups(
            group.get('groups', []), team_lookup, customers_lookup, bricks_lookup,
            streams_lookup, dependency_type_lookup
        )

        team_headcount = sum((team.get('teamHeadcount', {}) or {}).get('headcount', 0) for team in teams)
        direct_headcount = direct.get('headcount', 0)
        rolled_up = team_headcount + direct_headcount + sum(child.get('rollupHeadcount', 0) for child in child_groups)

        enriched_groups.append({
            'id': group.get('id', ''),
            'name': group.get('name', ''),
            'mission': group.get('mission', ''),
            'groupDirectHeadcount': {
                'headcount': direct_headcount,
                'description': direct.get('description', ''),
            },
            'teams': teams,
            'groups': child_groups,
            'teamHeadcount': team_headcount,
            'rollupHeadcount': rolled_up,
        })
    return enriched_groups


def flatten_teams(groups):
    teams = []
    for group, _ in iter_groups(groups):
        teams.extend(group.get('teams', []))
    return teams


def create_overview_docs(domain, docs_folder, teams_payload):
    if os.path.exists(docs_folder):
        shutil.rmtree(docs_folder)

    os.makedirs(os.path.join(docs_folder, 'landing_pages'), exist_ok=True)
    os.makedirs(os.path.join(docs_folder, 'icons'), exist_ok=True)
    copy_icons(os.path.join(templates_root, 'icons'), docs_folder)

    template = open(os.path.join(templates_root, 'index.html')).read()
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
                        .replace('${teams}', json.dumps(teams_payload)))


def create_landing_pages(domain, docs_folder, teams_payload):
    template = open(os.path.join(templates_root, 'landing_page.html')).read()

    for team in flatten_teams(teams_payload.get('groups', [])):
        landing_page_file = os.path.join(docs_folder, 'landing_pages', str(team['id']) + '.html')
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
                                'team_name': team.get('name', team['id'])
                            }))
                            .replace('${date}', date_string)
                            .replace('${domain_name}', domain['name'])
                            .replace('${team_name}', team.get('name', team['id']))
                            .replace('${team}', json.dumps(team)))


domain_id = domain['id']
teams_path = domain_source_path(domain_id, 'teams/teams.json')
if not os.path.exists(teams_path):
    raise SystemExit(f"Missing teams config for domain '{domain_id}'")

teams_payload = json.load(open(teams_path))
org_design = apply_shared_defaults(teams_payload.setdefault('orgDesign', {}), 'team-model.json', ('teamTypes', 'teamDependencyTypes'))

customers = load_json_if_exists(domain_source_path(domain_id, 'customers/customers.json'), [])
bricks = load_product_bricks_payload(domain_source_path(domain_id, 'product-bricks/product-bricks.json'))
streams_payload = load_product_streams_payload(domain_source_path(domain_id, 'product-bricks/product-stream.json'))

customers_lookup, _ = build_customers_lookup(customers)
bricks_lookup = build_bricks_lookup(bricks)
streams_lookup = build_streams_lookup(flatten_product_streams(streams_payload))
team_lookup = build_team_lookup(teams_payload)
dependency_type_lookup = {
    str(item.get('id', '')): item
    for item in org_design.get('teamDependencyTypes', [])
}

enriched_payload = {
    'orgDesign': org_design,
    'groups': enrich_groups(
        teams_payload.get('groups', []),
        team_lookup,
        customers_lookup,
        bricks_lookup,
        streams_lookup,
        dependency_type_lookup,
    ),
}

docs_folder = domain_docs_path(domain_id, 'teams') + '/'
create_overview_docs(domain, docs_folder, enriched_payload)
create_landing_pages(domain, docs_folder, enriched_payload)
