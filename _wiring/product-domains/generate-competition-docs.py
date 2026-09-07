import json
import os
import shutil

from domain_cli import load_domain_args
from generator_common import (
    domain_docs_path,
    domain_source_path,
    copy_files_into,
    enter_docs_root,
    render_breadcrumbs as render_breadcrumbs_from,
)

from generator_common import template_path

enter_docs_root()

templates_root = template_path('competition')

tabs_style = open(os.path.join(templates_root, '../_imports/tabs/style.html')).read()
tokens_style = open(os.path.join(templates_root, '../_imports/tokens/style.html')).read()
tabs_script = open(os.path.join(templates_root, '../_imports/tabs/script.html')).read()
common_style = open(os.path.join(templates_root, '../_imports/common/style.html')).read()
breadcrumbs_style = open(os.path.join(templates_root, '../_imports/breadcrumbs/style.html')).read()
breadcrumbs_script = open(os.path.join(templates_root, '../_imports/breadcrumbs/script.html')).read()

domain, _ = load_domain_args()


def render_breadcrumbs(template_name, replacements):
    return render_breadcrumbs_from(templates_root, template_name, replacements)


copy_folder_files = copy_files_into


def build_available_logos(logos_root):
    logos = {}
    if not os.path.exists(logos_root):
        return logos
    for filename in os.listdir(logos_root):
        if not os.path.isfile(os.path.join(logos_root, filename)):
            continue
        stem, _ = os.path.splitext(filename)
        logos[filename] = filename
        logos[stem] = filename
    return logos


def resolve_logo_filename(player, available_logos):
    candidates = []
    logo_value = player.get('logo')

    if isinstance(logo_value, str) and logo_value:
        candidates.append(os.path.basename(logo_value))
        stem, _ = os.path.splitext(os.path.basename(logo_value))
        if stem:
            candidates.append(stem)

    if isinstance(logo_value, dict):
        local_file = logo_value.get('local_file') or ''
        if local_file:
            candidates.append(os.path.basename(local_file))
            stem, _ = os.path.splitext(os.path.basename(local_file))
            if stem:
                candidates.append(stem)

    if player.get('id'):
        candidates.append(player['id'])

    for candidate in candidates:
        if candidate in available_logos:
            return available_logos[candidate]

    return None


def enrich_players(players, logos_root):
    available_logos = build_available_logos(logos_root)
    enriched = []
    for player in players:
        item = dict(player)
        resolved_logo = resolve_logo_filename(player, available_logos)
        item['logo_path'] = ('logos/' + resolved_logo) if resolved_logo else None
        enriched.append(item)
    return enriched


def create_overview_docs(domain_config, competition_payload, players):
    docs_folder = domain_docs_path(domain_config['id'], 'competition')
    if os.path.exists(docs_folder):
        shutil.rmtree(docs_folder)

    os.makedirs(docs_folder, exist_ok=True)
    copy_folder_files(os.path.join(templates_root, 'icons'), os.path.join(docs_folder, 'icons'))
    copy_folder_files(domain_source_path(domain_config['id'], 'business', 'logos'), os.path.join(docs_folder, 'logos'))

    template = open(os.path.join(templates_root, 'index.html')).read()
    payload = dict(competition_payload)
    payload['players'] = players

    with open(os.path.join(docs_folder, 'index.html'), 'w') as html_file:
        html_file.write(
            template
            .replace('${tabs_style}', tabs_style)
                        .replace('${tokens_style}', tokens_style)
            .replace('${tabs_script}', tabs_script)
            .replace('${breadcrumbs_style}', breadcrumbs_style)
            .replace('${breadcrumbs_script}', breadcrumbs_script)
            .replace('${breadcrumbs}', render_breadcrumbs('index_breadcrumbs.json', {
                'domain_name': domain_config['name']
            }))
            .replace('${domain_name}', domain_config['name'])
            .replace('${data}', json.dumps(payload))
        )

    return docs_folder


def create_landing_pages(domain_config, docs_folder, competition_scope, players):
    landing_pages_root = os.path.join(docs_folder, 'landing_pages')
    os.makedirs(landing_pages_root, exist_ok=True)

    template = open(os.path.join(templates_root, 'landing_page.html')).read()

    for player in players:
        with open(os.path.join(landing_pages_root, f"{player['id']}.html"), 'w') as html_file:
            html_file.write(
                template
                .replace('${common_style}', common_style)
                .replace('${tabs_style}', tabs_style)
                        .replace('${tokens_style}', tokens_style)
                .replace('${tabs_script}', tabs_script)
                .replace('${breadcrumbs_style}', breadcrumbs_style)
                .replace('${breadcrumbs_script}', breadcrumbs_script)
                .replace('${breadcrumbs}', render_breadcrumbs('landing_page_breadcrumbs.json', {
                    'domain_name': domain_config['name'],
                    'player_name': player['name']
                }))
                .replace('${player_name}', player['name'])
                .replace('${domain_name}', domain_config['name'])
                .replace('${player}', json.dumps(player))
                .replace('${scope}', json.dumps(competition_scope or {}))
            )


competition_path = domain_source_path(domain['id'], 'business', 'competition.json')
if not os.path.exists(competition_path):
    raise SystemExit(0)

competition = json.load(open(competition_path))
players = enrich_players(competition.get('players', []), domain_source_path(domain['id'], 'business', 'logos'))
docs_folder = create_overview_docs(domain, competition, players)
create_landing_pages(domain, docs_folder, competition.get('scope', {}), players)
