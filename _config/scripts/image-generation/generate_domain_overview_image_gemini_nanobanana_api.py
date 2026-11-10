#!/usr/bin/env python3
"""Illustrate one high-level overview of a product domain for its start page.

The picture explains what the domain is about at a glance: the products and their
building blocks inside, and the external world around them (customer groups,
delivery channels, external systems, competitors). The prompt is built from the
domain's own model files, and labels are capped so the image model can render them.

The image is saved as start/media/domain-overview.<format>, with its prompt beside
it; the start page shows it when present. Existing images are reused unless
--overwrite is given. --dry-run calls no API and writes nothing.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

TOOLKIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TOOLKIT / '_wiring'))
import project_paths
from domain_paths import list_domain_files

from generate_customer_icons_gemini_nanobanana_api import IMAGE_FORMATS, image_exists, write_bytes
from generate_tutorial_images_gemini_nanobanana_api import DEFAULT_MODEL, call_gemini_nanobanana_api

IMAGE_STEM = 'domain-overview'

# Labels per element kind. Image models garble text when there are many labels,
# so each kind shows only its largest or first entries.
LIMITS = {'customers': 4, 'products': 5, 'brick_groups': 4, 'channels': 3, 'external': 5, 'competitors': 3}

# Group names for specific brick externalSystems[].type values. Domains use their own
# type vocabulary, so several spellings map to one name.
EXTERNAL_TYPE_LABELS = {
    'erp': 'ERP systems',
    'data-provider': 'Data providers',
    'payment': 'Payment providers',
    'payments': 'Payment providers',
    'finance': 'Banks and accounting',
    'logistics': 'Shipping and logistics',
    'carrier': 'Shipping and logistics',
    'shipping-platform': 'Shipping and logistics',
    'channel': 'Sales channels',
    'marketplace': 'Sales channels',
    'commerce': 'Webshop platforms',
    'commerce-platform': 'Webshop platforms',
    'analytics': 'Analytics',
    'infrastructure': 'Cloud infrastructure',
    'identity': 'Identity providers',
    'communication': 'Messaging services',
    'messaging': 'Messaging services',
    'support': 'Helpdesk tools',
    'ai': 'AI models',
    'device': 'Hardware devices',
    'hardware': 'Hardware devices',
    'sibling': 'Group companies',
    'network': 'Partner networks',
    'ci-cd': 'CI/CD',
    'store-pos': 'Store POS',
    'cicd': 'CI/CD',
}
# Types that name a role rather than a kind of system ("data", "partner"). Their label is
# the shortest concrete system name instead, and they rank after the specific types.
# Any "...-consumer" type also names a role (who uses the domain), not a system kind.
GENERIC_EXTERNAL_TYPES = {'data', 'partner', 'system', 'service', 'consumer', 'data-consumer',
                          'customer-system', 'other', 'operational', 'integration', 'external',
                          'external-system', 'external-service'}
# People and customer devices are already shown through the customer groups.
SKIPPED_EXTERNAL_TYPES = {'channel-consumer', 'user'}
# The company a domain is modeled on is listed in its competition file for context,
# but it is the domain itself, not an alternative to it.
MODELED_COMPANY_CATEGORIES = {'modeled-company', 'reference-company'}
# Words a label must not end on after it is cut to length ("Adoption and").
DANGLING_WORDS = {'and', 'or', 'of', 'for', 'the', 'with', 'to', 'in', 'on', 'a', 'an', 'by', 'via'}


def is_generic_external_type(kind):
    return kind in GENERIC_EXTERNAL_TYPES or kind.endswith('-consumer') or kind.endswith(' consumer')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--domain', help='Domain ID or domain folder; omit to process every domain.')
    scope.add_argument('--domain-dir', type=Path, help='Full domain folder; also selects the data project.')
    parser.add_argument('--project', type=Path, help='Data project root (default: current project).')
    parser.add_argument('--scene', help='Replace the default composition directions (labels still come from the model).')
    parser.add_argument('--limit', type=int, default=0, help='Maximum new images; 0 means all.')
    parser.add_argument('--model', default=DEFAULT_MODEL, help='Gemini image model.')
    parser.add_argument('--aspect-ratio', choices=('16:9', '3:2', '4:3', '1:1'), default='16:9')
    parser.add_argument('--image-size', choices=('1K', '2K', '4K'), default='2K')
    parser.add_argument('--max-width', type=int, default=1600,
                        help='Shrink the saved image to this width as JPEG with macOS sips; 0 keeps the original.')
    parser.add_argument('--dry-run', action='store_true', help='Print actions without writes or API calls.')
    parser.add_argument('--show-prompts', action='store_true', help='Include complete prompts in the output.')
    existing = parser.add_mutually_exclusive_group()
    existing.add_argument('--skip-existing', action='store_true', help='Reuse existing images (the default).')
    existing.add_argument('--overwrite', action='store_true', help='Regenerate existing overview images.')
    parser.add_argument('--api-key-env', choices=('GEMINI_API_KEY', 'GOOGLE_API_KEY'), default='GEMINI_API_KEY')
    parser.add_argument('--max-retries', type=int, default=4)
    parser.add_argument('--retry-delay-seconds', type=float, default=5.0)
    args = parser.parse_args(argv)
    for name in ('limit', 'max_retries', 'retry_delay_seconds', 'max_width'):
        if not math.isfinite(getattr(args, name)) or getattr(args, name) < 0:
            parser.error(f'--{name.replace("_", "-")} must be finite and nonnegative')
    return args


def load(domain_dir, relative, default):
    path = domain_dir / relative
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def short_label(text, limit=40):
    """Drop parentheticals and trailing detail so labels stay short and legible."""
    text = re.sub(r'\s*\([^)]*\)', '', str(text or '')).strip()
    text = re.split(r'\s+[-–—]\s+', text)[0].strip()
    if len(text) <= limit:
        return text
    # Cut at a word boundary without an ellipsis; models tend to copy "…" into the image.
    words = text[:limit + 1].rsplit(' ', 1)[0].rstrip(' ,;/&').split()
    while len(words) > 1 and words[-1].lower() in DANGLING_WORDS:
        words.pop()
    return ' '.join(words).rstrip(' ,;/&')


def first_sentence(text, limit=160):
    text = ' '.join(str(text or '').split())
    # A sentence ends at ". " or "; " before a capital letter, so "incl. carriers" stays whole.
    text = re.split(r'(?<=[.;:])\s+(?=[A-Z])', text)[0].rstrip('.;:')
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def external_label(kind):
    if kind in EXTERNAL_TYPE_LABELS:
        return EXTERNAL_TYPE_LABELS[kind]
    if len(kind) <= 3:
        return kind.upper()
    words = kind.replace('-', ' ').replace('_', ' ').split()
    return ' '.join(word if index and word in DANGLING_WORDS else word.capitalize()
                    for index, word in enumerate(words))


def role_label(systems, limit=32):
    """A concrete system name for a role-like type, or None when every name would be cut."""
    fitting = [name for name in systems if name and len(name) <= limit]
    return min(fitting, key=len) if fitting else None


def unique(values):
    seen, result = set(), []
    for value in values:
        if value and value.lower() not in seen:
            seen.add(value.lower())
            result.append(value)
    return result


def walk_groups(groups, child_key):
    for group in groups or []:
        yield group, group.get(child_key, []) or []
        yield from walk_groups(group.get('subGroups', []), child_key)


def count_items(group, child_key):
    return len(group.get(child_key, []) or []) + sum(count_items(sub, child_key) for sub in group.get('subGroups', []) or [])


def collect_model(domain_dir):
    """Summarize the domain into named elements, each list capped by LIMITS."""
    config = load(domain_dir, 'start/config.json', {})
    customers = load(domain_dir, 'customers/customers.json', [])
    competition = load(domain_dir, 'business/competition.json', {})
    products = load(domain_dir, 'product-deployments/products.json', {})
    deployment = load(domain_dir, 'product-deployments/deployment.json', {})
    bricks = load(domain_dir, 'product-bricks/product-bricks.json', {})
    data_assets = load(domain_dir, 'data/data-assets.json', {})

    customer_groups = [group for group in customers if group.get('customers')]
    customer_groups.sort(key=lambda group: -len(group['customers']))
    customer_labels = unique(short_label(group.get('group'), 48) for group in customer_groups)[:LIMITS['customers']]
    # Group names and sizes only: when told the individual roles, models label each person.
    customer_context = [f"{group.get('group')} ({len(group['customers'])} customer roles)"
                        for group in customer_groups if short_label(group.get('group'), 48) in customer_labels]

    product_list = (products.get('portfolio') or {}).get('products', []) or []
    # Product cards hold two or three lines, so product names may be longer than other labels.
    product_labels = unique(short_label(p.get('name'), 56) for p in product_list)[:LIMITS['products']]
    product_context = [f"{p.get('name')}" + (f" ({p['type']})" if p.get('type') else '') +
                       (f": {first_sentence(p['description'])}" if p.get('description') else '')
                       # Only the labelled products: models draw every product they are told about.
                       for p in product_list if short_label(p.get('name'), 56) in product_labels]

    root_bricks = (bricks.get('rootGroups') or []) if isinstance(bricks, dict) else []
    brick_total = sum(count_items(group, 'bricks') for group in root_bricks)
    brick_groups = sorted(root_bricks, key=lambda group: -count_items(group, 'bricks'))
    brick_labels = unique(short_label(group.get('name')) for group in brick_groups)[:LIMITS['brick_groups']]

    external = {}
    for _, items in walk_groups(root_bricks, 'bricks'):
        for brick in items:
            for key in ('externalSystemsThisBrickDependsOn', 'externalSystemsDependingOnThisBrick'):
                for system in brick.get(key, []) or []:
                    if not isinstance(system, dict) or system.get('type') in SKIPPED_EXTERNAL_TYPES:
                        continue
                    kind = str(system.get('type') or 'other').lower()
                    # Keep whole names: a cut name ("Airports and venue operating") is not a label.
                    external.setdefault(kind, []).append(short_label(system.get('system'), 200))
    # Specific types first (most systems first), then generic ones under a concrete system name.
    external_kinds = sorted(external, key=lambda kind: (is_generic_external_type(kind), -len(external[kind])))
    external_labels = unique(
        role_label(external[kind]) if is_generic_external_type(kind) else external_label(kind)
        for kind in external_kinds)[:LIMITS['external']]
    # A domain that types most systems with one role ("integration") would otherwise show a single
    # tile, which models repeat; fill the free tiles with further concrete names, most used first.
    if len(external_labels) < LIMITS['external']:
        counts = {}
        for kind in external_kinds:
            if is_generic_external_type(kind):
                for name in external[kind]:
                    counts[name] = counts.get(name, 0) + 1
        extra = sorted((name for name in counts if len(name) <= 32), key=lambda name: (-counts[name], len(name)))
        external_labels = unique(external_labels + extra)[:LIMITS['external']]
    external_context = [f"{external_label(kind)}: " + ', '.join(unique(external[kind])[:4])
                        for kind in external_kinds]

    channel_groups = [group for group in deployment.get('channels', []) or [] if group.get('channels')]
    channel_labels = unique(short_label(group.get('groupName') or group.get('groupId'))
                            for group in channel_groups)[:LIMITS['channels']]
    channel_context = [f"{group.get('groupName')}: " + ', '.join(
        c.get('subChannelName') or c.get('subChannelId', '') for c in group['channels']) for group in channel_groups
        if short_label(group.get('groupName') or group.get('groupId')) in channel_labels]

    rank = {'global_leader': 0, 'leader': 0, 'regional': 1, 'challenger': 2}
    players = [p for p in competition.get('players', []) or [] 
               if str(p.get('category') or '').lower().replace('_', '-') not in MODELED_COMPANY_CATEGORIES]
    players = sorted(players, key=lambda p: rank.get(p.get('category'), 3))
    competitor_labels = unique(short_label(p.get('name'), 32) for p in players)[:LIMITS['competitors']]

    data_groups = [group.get('name') for group in data_assets.get('rootGroups', []) or [] if group.get('name')]

    return {
        'name': config.get('name') or domain_dir.name,
        'description': config.get('description', ''),
        'customers': customer_labels, 'customer_context': customer_context,
        'products': product_labels, 'product_context': product_context,
        'brick_groups': brick_labels, 'brick_total': brick_total,
        'external': external_labels, 'external_context': external_context,
        'channels': channel_labels, 'channel_context': channel_context,
        'competitors': competitor_labels, 'competitor_count': len(players),
        'data_groups': data_groups,
    }


SCENE_INTRO = 'One wide "context map" read from left to right:'
SCENE_CUSTOMERS = """- Left, outside the boundary: each customer group as ONE small cluster of two or three generic people
  with exactly one label, the group name. Do not split a group into individual roles or label single people."""
SCENE_INSIDE = """- Center: one large rounded boundary for the domain. Inside it, the products as a row of distinct
  product cards on top; below them ONE shared row of building-block piles, one pile per product brick
  group, spanning the full width under all products. Products are assembled from many groups and groups
  are shared by many products, so do not pair a product with a group: no columns and no product-to-group
  arrows; the product row simply rests on the brick row. Below the bricks a shared data layer (a simple
  database shape) used by all brick groups."""
SCENE_CHANNELS = """- Along the bottom edge of the boundary: the delivery channels as a base strip of runtime platforms
  (servers, cloud, app stores) that the bricks are deployed to and the products are delivered through."""
SCENE_NO_CHANNELS = '- No delivery-channel strip: the boundary ends below the data layer.'
SCENE_EXTERNAL = """- Right, outside the boundary: the external systems as separate service tiles, each connected to the
  boundary with a two-way connector line."""
SCENE_NO_EXTERNAL = ('- No external systems: leave the area right of the boundary empty apart from the competitors; '
                     'draw no service tiles or connector lines there.')
SCENE_COMPETITORS = """- Bottom right, set apart and smaller: competitors as alternative storefronts the customers could choose instead,
  with a thin dashed line towards the customers, not connected to the domain."""


def default_scene(model):
    """The composition, leaving out the parts the domain does not model so none get invented."""
    has_channels, has_external = bool(model.get('channels')), bool(model.get('external'))
    arrows = ['customers <-> products', 'the brick row reads and writes the data layer']
    if has_channels:
        arrows.append('bricks are deployed onto the delivery channels')
    if has_external:
        arrows.append('the domain exchanges data with the external systems')
    parts = [SCENE_INTRO, SCENE_CUSTOMERS, SCENE_INSIDE,
             SCENE_CHANNELS if has_channels else SCENE_NO_CHANNELS,
             SCENE_EXTERNAL if has_external else SCENE_NO_EXTERNAL]
    if model.get('competitors'):
        parts.append(SCENE_COMPETITORS)
    parts.append('- Arrows: ' + '; '.join(arrows) + '. No other arrows.')
    return '\n'.join(parts)


DEFAULT_SCENE = default_scene({'channels': [1], 'external': [1], 'competitors': [1]})


def build_prompt(model, scene=None, aspect_ratio='16:9'):
    def bullets(values):
        return '\n'.join(f'  - {value}' for value in values) or '  - (none)'

    labels = [('Customer groups (left)', model['customers']),
              ('Delivery channels (bottom edge of the boundary)', model['channels']),
              ('Products (center, top)', model['products']),
              ('Product brick groups (center, building blocks)', model['brick_groups']),
              ('Data layer (center, bottom)', ['Shared data'] if model['data_groups'] else []),
              ('External systems (right)', model['external']),
              ('Competitors (bottom right, apart)', (['Competitors'] + model['competitors']) if model['competitors'] else [])]
    label_text = '\n'.join(f'{title}:\n{bullets(values)}' for title, values in labels if values)
    context = '\n'.join(filter(None, [
        f"What the domain is: {model['description']}",
        'Customers: ' + '; '.join(model['customer_context']) if model['customer_context'] else '',
        'Products: ' + '; '.join(model['product_context']) if model['product_context'] else '',
        f"Product bricks: {model['brick_total']} building blocks in groups: " + ', '.join(model['brick_groups'])
        if model['brick_groups'] else '',
        'Data: ' + ', '.join(model['data_groups']) if model['data_groups'] else '',
        'Delivery channels: ' + '; '.join(model['channel_context']) if model['channel_context'] else '',
        'External systems: ' + '; '.join(model['external_context']) if model['external_context'] else '',
        f"Competitors: {model['competitor_count']} players, for example " + ', '.join(model['competitors'])
        if model['competitors'] else '',
    ]))
    return f'''Draw the picture described below for the top of a product-domain website.
Domain: {model['name']}
Reader: a product manager or engineer new to this domain who needs the big picture in ten seconds.

Background (for understanding only; do not write it in the image):
{context}

Composition:
{scene or default_scene(model)}

Text in the image: write the domain name "{model['name']}" once as a small title at the top of the
boundary, plus exactly these labels, spelled exactly as given, each next to its element:
{label_text}
Write no other text anywhere: no headline or caption above, below, or beside the boundary, no
section captions (such as "Runtime platform", "Deploy", "Product", or "Delivery channels"), no
sub-labels inside tiles, no job titles or descriptions under people,
no arrow labels (such as "Read", "Write", or "Deployment"), numbers, legends, placeholder text (such as "Search..."), or invented names. Never
write the words overview, diagram, illustration, or picture.

Style:
- Aspect ratio {aspect_ratio}, generous margins, everything inside the frame.
- Background: pure white (#FFFFFF) across the whole canvas, with no cream, beige, paper tint,
  texture, or vignette. Only the domain boundary and the tiles may have a light fill.
- Clean flat editorial illustration with isometric hints: crisp navy outlines, restrained teal, blue,
  and warm amber accents, soft shadows, no photorealism and no 3D rendering.
- Outside elements and inside elements must be clearly distinguishable: the boundary separates them.
- Labels in a clear sans-serif, large enough to read at half size on a laptop screen.
- Generic, inclusive people and generic devices. No brand logos, trademarks, or watermarks anywhere,
  even for the named competitors, sales channels, and external systems: draw generic icons
  (a shopping cart, a storefront, a truck) instead of company marks. This includes app-store, browser,
  payment-card, and social-network marks, and product cards drawn as wordmarks.
'''.strip()


def overview_alt(model):
    parts = [f"Overview of {model['name']}"]
    for title, values in (('customers', model['customers']), ('products', model['products']),
                          ('building blocks', model['brick_groups']), ('external systems', model['external'])):
        if values:
            parts.append(f"{title}: {', '.join(values)}")
    return '. '.join(parts) + '.'


def shrink_image(image_bytes, max_width):
    """Return (bytes, format) of a JPEG at most max_width wide, or None when sips is unavailable.

    Providers return 2.7K-wide images of several megabytes; a start page hero needs far less.
    sips ships with macOS; elsewhere the original image is kept.
    """
    sips = shutil.which('sips')
    if not max_width or not sips:
        return None
    with tempfile.TemporaryDirectory() as folder:
        source, output = Path(folder) / 'source', Path(folder) / 'output.jpg'
        source.write_bytes(image_bytes)
        width = subprocess.run([sips, '-g', 'pixelWidth', str(source)], capture_output=True, text=True)
        match = re.search(r'pixelWidth:\s*(\d+)', width.stdout)
        command = [sips, '-s', 'format', 'jpeg', '-s', 'formatOptions', '85']
        if match and int(match.group(1)) > max_width:
            command += ['--resampleWidth', str(max_width)]
        result = subprocess.run(command + [str(source), '--out', str(output)], capture_output=True, text=True)
        if result.returncode or not image_exists(output):
            print(f'  Could not shrink the image with sips; keeping the original. {result.stderr.strip()}', flush=True)
            return None
        return output.read_bytes(), 'jpg'


def existing_image(start_dir):
    for fmt in IMAGE_FORMATS:
        candidate = start_dir / 'media' / f'{IMAGE_STEM}.{fmt}'
        if image_exists(candidate):
            return candidate
    return None


def run_generation(args, api_key):
    domain_id, domain_dir = project_paths.domain_selection(args.domain, args.domain_dir)
    project = project_paths.resolve_project_root(args.project, domain_dir)
    project_paths.configure(project)
    configs = list_domain_files('start/config.json', domain_dir.name if domain_dir else domain_id,
                                project_paths.DOMAINS_ROOT)
    if not configs:
        print('No domains found for the selected scope.')
        return 0
    prepared = []
    for config_path in configs:
        start_dir = config_path.parent
        model = collect_model(start_dir.parent)
        if not (model['products'] or model['brick_groups']):
            print(f'Skip (no products or bricks yet): {start_dir.parent.name}')
            continue
        prepared.append((start_dir, model, build_prompt(model, args.scene, args.aspect_ratio)))
    needs_api = any(args.overwrite or not existing_image(start_dir) for start_dir, _, _ in prepared)
    if needs_api and not (args.dry_run or api_key):
        raise ValueError(f'Set {args.api_key_env} locally, or use --dry-run.')

    generated = 0
    for start_dir, model, prompt in prepared:
        current = existing_image(start_dir)
        should_generate = (args.overwrite or not current) and (not args.limit or generated < args.limit)
        target = start_dir / 'media' / f'{IMAGE_STEM}.png'
        action = 'Generate' if should_generate else ('Reuse' if current else 'Skip (limit reached)')
        print(f'{action}: {start_dir.parent.name}\n  {current or target}', flush=True)
        if args.show_prompts:
            print(prompt, flush=True)
        if not should_generate:
            continue
        if not args.dry_run:
            image = call_gemini_nanobanana_api(api_key, SimpleNamespace(prompt=prompt), args)
            image_bytes, output_format = shrink_image(image.image_bytes, args.max_width) or (
                image.image_bytes, image.output_format)
            path = target.with_suffix(f'.{output_format}')
            write_bytes(path, image_bytes)
            for fmt in IMAGE_FORMATS:  # Keep exactly one overview image per domain.
                stale = path.with_suffix(f'.{fmt}')
                if stale != path and stale.exists():
                    stale.unlink()
            write_bytes(path.with_name(f'{IMAGE_STEM}.prompt.txt'), (prompt + '\n').encode('utf-8'))
            write_bytes(path.with_name(f'{IMAGE_STEM}.alt.txt'), (overview_alt(model) + '\n').encode('utf-8'))
            print(f'  Saved: {path}', flush=True)  # The provider decides the format.
        generated += 1
    verb = 'Would generate' if args.dry_run else 'Generated'
    print(f'{verb} {generated} domain overview image(s). Rebuild the start section to show them.')
    return 0


def main():
    args = parse_args()
    try:
        return run_generation(args, os.environ.get(args.api_key_env, '').strip())
    except (OSError, RuntimeError, ValueError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
