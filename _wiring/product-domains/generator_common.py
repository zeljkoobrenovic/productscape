"""Shared helpers for the product-domain doc generators.

Generators resolve command-line inputs before entering the output directory.
Sources and templates use absolute paths; published paths retain the grouped
site layout.
"""
import datetime
import json
import os
import shutil
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO_ROOT, '_wiring'))
import domain_paths
import project_paths
from project_paths import template_path, navigation_path

CUSTOMER_ICON_MAP = {
    'house-search': 'seeker.png',
    'owner-key': 'owner.png',
    'briefcase-building': 'intermediary.png',
}


def enter_docs_root():
    docs_root = str(project_paths.DOCS_ROOT)
    os.makedirs(docs_root, exist_ok=True)
    os.chdir(docs_root)


def domain_source_path(domain_id, *parts):
    return domain_paths.domain_source_path(domain_id, *parts, domains_root=project_paths.DOMAINS_ROOT)


def domain_docs_path(domain_id, *parts):
    return domain_paths.domain_docs_path(domain_id, *parts, domains_root=project_paths.DOMAINS_ROOT)


def today_string():
    return datetime.date.today().strftime('%Y-%m-%d')


def read_import(templates_root, name):
    """Read a shared partial from _templates/_imports, e.g. read_import(root, 'tabs/style')."""
    return open(os.path.join(templates_root, '..', '_imports', name + '.html')).read()


def load_json_if_exists(path, default_value):
    if os.path.exists(path):
        return json.load(open(path))
    return default_value


def load_first_existing(paths, default_value):
    for path in paths:
        if os.path.exists(path):
            return json.load(open(path))
    return default_value


def load_json_items_from_paths(paths, default_value):
    """First existing JSON file; a {'items': [...]} wrapper is unwrapped."""
    for path in paths:
        if os.path.exists(path):
            payload = json.load(open(path))
            if isinstance(payload, dict) and isinstance(payload.get('items'), list):
                return payload.get('items')
            return payload
    return default_value


def copy_icons(icons_path, docs_folder, recursive=False):
    """Copy icon files into <docs_folder>/icons (which must already exist for
    the flat variant; the recursive variant creates subfolders as needed)."""
    if not os.path.exists(icons_path):
        return
    target_root = os.path.join(docs_folder, 'icons')
    if recursive:
        for root, _, filenames in os.walk(icons_path):
            rel_root = os.path.relpath(root, icons_path)
            target_dir = target_root if rel_root == '.' else os.path.join(target_root, rel_root)
            os.makedirs(target_dir, exist_ok=True)
            for filename in filenames:
                src = os.path.join(root, filename)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(target_dir, filename))
    else:
        for filename in os.listdir(icons_path):
            src = os.path.join(icons_path, filename)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(target_root, filename))


def copy_files_into(src_folder, dst_folder):
    """Flat-copy the files of src_folder directly into dst_folder."""
    if not os.path.exists(src_folder):
        return
    os.makedirs(dst_folder, exist_ok=True)
    for filename in os.listdir(src_folder):
        src = os.path.join(src_folder, filename)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_folder, filename))


def reset_output_folder(docs_folder, *subfolders):
    """Wipe and recreate a generator's output folder (call AFTER parsing inputs)."""
    if os.path.exists(docs_folder):
        shutil.rmtree(docs_folder)
    os.makedirs(docs_folder, exist_ok=True)
    for subfolder in subfolders:
        os.makedirs(os.path.join(docs_folder, subfolder), exist_ok=True)


def render_breadcrumbs(templates_root, template_name, replacements):
    breadcrumbs = open(os.path.join(templates_root, template_name)).read()
    for key, value in replacements.items():
        breadcrumbs = breadcrumbs.replace('${' + key + '}', value)
    return breadcrumbs


def normalize_icon_name(icon_name, fallback='customer.png'):
    value = (icon_name or fallback).strip()
    if not value:
        value = fallback
    while value.endswith('.png.png'):
        value = value[:-4]
    while value.endswith('.svg.png'):
        value = value[:-4]
    if '.' in value:
        return value
    return value + '.png'


def iter_group_tree(groups, ancestors=None):
    """Yield (group, ancestors) for every group in a recursive 'groups' tree."""
    ancestors = ancestors or []
    for group in groups or []:
        yield group, ancestors
        for descendant in iter_group_tree(group.get('groups', []), ancestors + [group]):
            yield descendant


def collect_kpis(node, target):
    if not node:
        return
    if node.get('name'):
        target[node['name'].lower()] = {
            'name': node.get('name', ''),
            'description': node.get('description', ''),
            'unit': node.get('unit', ''),
            'currentValue': node.get('currentValue', ''),
            'link': node.get('link', ''),
            'linkLabel': node.get('linkLabel', ''),
        }
    for child in node.get('children', []):
        collect_kpis(child, target)


def build_customers_lookup(customers):
    """Return (lookup, kpi_lookup) keyed by customer id."""
    lookup = {}
    kpi_lookup = {}

    for group in customers:
        group_name = group.get('group', '')
        for customer in group.get('customers', []):
            lookup[customer['id']] = {
                'id': customer['id'],
                'name': customer.get('name', customer['id']),
                'group': group_name,
                'icon': normalize_icon_name(
                    CUSTOMER_ICON_MAP.get(customer.get('icon', ''), customer.get('icon', 'customer.png'))
                ),
            }

            pyramids = customer.get('kpiPyramids', {})
            customer_map = {}
            business_map = {}
            collect_kpis(pyramids.get('customerOutcomes', {}).get('top'), customer_map)
            collect_kpis(pyramids.get('businessOutcomes', {}).get('top'), business_map)
            for branch in pyramids.get('customerOutcomes', {}).get('branches', []):
                collect_kpis(branch, customer_map)
            for branch in pyramids.get('businessOutcomes', {}).get('branches', []):
                collect_kpis(branch, business_map)
            kpi_lookup[customer['id']] = {
                'customer': customer_map,
                'business': business_map,
            }

    return lookup, kpi_lookup
