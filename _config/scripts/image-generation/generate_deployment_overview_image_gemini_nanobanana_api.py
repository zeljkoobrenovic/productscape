#!/usr/bin/env python3
"""Illustrate how a domain's products map onto its deployment channels.

One picture for the top of the Product Deployments overview: the products as a row
of cards, the deployment channel groups as lanes beneath them with their channels,
and the bricks the products share. It shows structure only, never which product runs
in which lane: across test runs image models misplaced individual product-to-lane
lines and brackets, and the page's heatmap and matrix carry those exact links. The
prompt is built from product-deployments/products.json and deployment.json.

The image is saved as product-deployments/media/deployment-overview.<format>, with
its prompt and alt text beside it; the deployments page shows it when present.
Existing images are reused unless --overwrite is given. --dry-run calls no API and
writes nothing.
"""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_domain_overview_image_gemini_nanobanana_api as overview
from generate_customer_icons_gemini_nanobanana_api import IMAGE_FORMATS, image_exists, write_bytes
from generate_tutorial_images_gemini_nanobanana_api import DEFAULT_MODEL, call_gemini_nanobanana_api

project_paths = overview.project_paths
list_domain_files = overview.list_domain_files
first_sentence, short_label, unique, load = overview.first_sentence, overview.short_label, overview.unique, overview.load

IMAGE_STEM = 'deployment-overview'
SECTION = 'product-deployments'

# Image models garble crowded text, so each kind shows only its largest entries.
LIMITS = {'products': 9, 'groups': 4, 'channels_per_group': 3, 'channels': 8, 'shared_bricks': 3}


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
    existing.add_argument('--overwrite', action='store_true', help='Regenerate existing deployment images.')
    parser.add_argument('--api-key-env', choices=('GEMINI_API_KEY', 'GOOGLE_API_KEY'), default='GEMINI_API_KEY')
    parser.add_argument('--max-retries', type=int, default=4)
    parser.add_argument('--retry-delay-seconds', type=float, default=5.0)
    args = parser.parse_args(argv)
    for name in ('limit', 'max_retries', 'retry_delay_seconds', 'max_width'):
        if not math.isfinite(getattr(args, name)) or getattr(args, name) < 0:
            parser.error(f'--{name.replace("_", "-")} must be finite and nonnegative')
    return args


TRAILING_WORDS = {'and', 'or', 'of', 'the', 'for', 'with', 'to', 'in', 'on', 'a', '&'}


def compact_label(text, limit=32):
    """short_label, but long names keep their head phrase instead of ending mid-phrase."""
    label = short_label(text, 200)
    if len(label) > limit:
        # A one-word head ("Platform" of "Platform and Integration Services") loses the meaning.
        for separator in (',', ' and ', ' & '):
            head = label.split(separator)[0].strip()
            if len(head.split()) >= 2 and len(head) <= limit:
                return head
        label = short_label(label, limit)
    words = label.rstrip(' ,;').split()
    while len(words) > 1 and words[-1].lower().rstrip(',') in TRAILING_WORDS:
        words.pop()
    return ' '.join(words).rstrip(',')


def collect_model(domain_dir):
    """Summarize products, channel lanes, shared bricks, and (for alt text) product-lane use."""
    config = load(domain_dir, 'start/config.json', {})
    products = load(domain_dir, f'{SECTION}/products.json', {})
    deployment = load(domain_dir, f'{SECTION}/deployment.json', {})

    product_list = [p for p in (products.get('portfolio') or {}).get('products', []) or [] if p.get('id')]
    names = {p['id']: compact_label(p.get('name') or p['id'], 44) for p in product_list}

    groups, bricks = [], {}
    for raw in deployment.get('channels', []) or []:
        channels, product_bricks = [], {}
        for channel in raw.get('channels', []) or []:
            deployed = [d for d in channel.get('deployedBricks', []) or [] if isinstance(d, dict) and d.get('brickId')]
            channels.append({'name': compact_label(channel.get('subChannelName') or channel.get('subChannelId'), 36),
                             'bricks': len(deployed)})
            for item in deployed:
                brick = bricks.setdefault(item['brickId'], {'name': compact_label(item.get('brickName') or item['brickId'], 44),
                                                           'products': set()})
                for use in item.get('usedInProducts', []) or []:
                    if use.get('productId') in names:
                        brick['products'].add(use['productId'])
                        product_bricks.setdefault(use['productId'], set()).add(item['brickId'])
        if channels:
            groups.append({'name': short_label(raw.get('groupName') or raw.get('groupId'), 36),
                           'description': first_sentence(raw.get('description', '')),
                           'channels': channels, 'product_bricks': product_bricks})

    footprint = {pid: len(set().union(*(g['product_bricks'].get(pid, set()) for g in groups))) if groups else 0
                 for pid in names}
    # Caps drop the smallest entries; what is shown keeps the authored order, like the page.
    largest_products = {p['id'] for p in sorted(product_list, key=lambda p: -footprint[p['id']])[:LIMITS['products']]}
    shown_products = [p for p in product_list if p['id'] in largest_products]
    shown_ids = {p['id'] for p in shown_products}

    largest_groups = sorted(groups, key=lambda g: -sum(c['bricks'] for c in g['channels']))[:LIMITS['groups']]
    shown_groups = [g for g in groups if any(g is kept for kept in largest_groups)]
    budget = LIMITS['channels']
    for group in shown_groups:
        ranked = sorted(group['channels'], key=lambda c: -c['bricks'])
        group['shown_channels'] = unique(c['name'] for c in ranked)[:min(LIMITS['channels_per_group'], max(budget, 0))]
        budget -= len(group['shown_channels'])

    # Which product runs in which lane; used only for the alt text, never drawn.
    uses = [{'product': names[p['id']], 'lane': g['name']}
            for p in shown_products for g in shown_groups if g['product_bricks'].get(p['id'])]

    # Bricks every deployed product uses, else the most shared ones (drawn without attribution).
    deployed_ids = {pid for pid in shown_ids if footprint[pid]}
    multi = sorted((b for b in bricks.values() if len(b['products'] & shown_ids) > 1),
                   key=lambda b: (-len(b['products'] & shown_ids), b['name']))
    common = [b['name'] for b in multi if len(deployed_ids) > 1 and deployed_ids <= b['products']]
    shared_by_all = bool(common)
    shared = (common or [b['name'] for b in multi])[:LIMITS['shared_bricks']]

    return {
        'name': config.get('name') or domain_dir.name,
        'description': config.get('description', ''),
        'products': [names[p['id']] for p in shown_products],
        'product_context': [f"{p.get('name')}" + (f" ({p['type']})" if p.get('type') else '') +
                            (f": {first_sentence(p['description'])}" if p.get('description') else '') for p in product_list],
        'unmapped': [names[pid] for pid in names if pid in shown_ids and not footprint[pid]],
        'groups': [{'name': g['name'], 'channels': g['shown_channels'], 'description': g['description']}
                   for g in shown_groups],
        'uses': uses,
        'shared': shared,
        'shared_by_all': shared_by_all,
        'brick_total': len(bricks),
        'shared_total': sum(1 for b in bricks.values() if len(b['products']) > 1),
    }


DEFAULT_SCENE = '''One wide picture read from top to bottom, in three bands:
- Top band: the products as a single row of distinct product cards, evenly spaced, each with a simple
  generic product icon and its label only: no subtitle, category, or description under the name.
- Middle band: the listed shared bricks as one continuous row of building blocks spanning the full width
  under the product row, with each listed name written once along it. If none are listed, leave it out.
- Bottom band: the deployment channel groups as wide horizontal lanes stacked in the listed order, the first
  lane on top. Each lane is a long rounded band with a light tint and its group label at the left end; inside
  it, its channels as small runtime-platform tiles (a server, a cloud, a browser window, a phone, a gear for
  internal tools), each with its label.
- Connection: ONE broad, soft, semi-transparent band flowing down from the whole product row to the whole
  stack of lanes, meaning "the products are deployed onto these platforms".
- Draw NO individual lines, arrows, or brackets between a specific product and a specific lane, channel, or
  brick, and none between lanes or between products. Each label appears exactly once.'''


def build_prompt(model, scene=None, aspect_ratio='16:9'):
    def bullets(values):
        return '\n'.join(f'  - {value}' for value in values) or '  - (none)'

    lane_text = '\n'.join(f'  - Lane "{g["name"]}" with channel tiles: ' + ', '.join(f'"{c}"' for c in g['channels'])
                          for g in model['groups']) or '  - (none)'
    shared_title = ('Bricks used by every product' if model['shared_by_all']
                    else 'Most shared bricks') + ' (one continuous row under the products)'
    unmapped = (f"\nProducts not yet deployed (draw their cards with a dashed outline): "
                + ', '.join(f'"{p}"' for p in model['unmapped'])) if model['unmapped'] else ''
    context = '\n'.join(filter(None, [
        f"What the domain is: {model['description']}",
        'Products: ' + '; '.join(model['product_context']) if model['product_context'] else '',
        'Channel groups: ' + '; '.join(f"{g['name']}: {g['description']}" for g in model['groups'] if g['description']),
        f"Product bricks deployed: {model['brick_total']}, of which {model['shared_total']} are used by more than one product.",
    ]))
    return f'''Draw the picture described below for the top of a product-deployments web page.
Domain: {model['name']}
Reader: a product manager or engineer who wants the big picture in ten seconds: which products there are,
what they share, and which platforms they are deployed to.

Background (for understanding only; do not write it in the image):
{context}

Composition:
{scene or DEFAULT_SCENE}

Products (top row, left to right):
{bullets(model['products'])}{unmapped}

{shared_title}:
{bullets(f'"{name}"' for name in model['shared'])}

Deployment lanes (bottom, first lane on top):
{lane_text}

Text in the image: exactly the product, brick, lane, and channel labels above, spelled exactly as given,
each next to its element. Write no other text anywhere: no title, headline, or caption, no legend, no numbers,
no section captions (such as "Products", "Shared", or "Channels"), and no invented names. Never write the
words overview, diagram, illustration, deployment map, or picture.

Style:
- Aspect ratio {aspect_ratio}, generous margins, everything inside the frame.
- Background: pure white (#FFFFFF) across the whole canvas, with no cream, beige, paper tint,
  texture, or vignette. Only cards, the brick row, lanes, and tiles may have a light fill.
- Clean flat editorial illustration with isometric hints: crisp navy outlines, restrained blue,
  teal, and warm amber accents (one tint per lane), soft shadows, no photorealism and no 3D rendering.
- Labels in a clear sans-serif, large enough to read at half size on a laptop screen.
- No brand logos, trademarks, or watermarks anywhere: draw generic icons instead of company marks.
'''.strip()


def deployment_alt(model):
    parts = [f"Deployment map of {model['name']}"]
    if model['products']:
        parts.append('products: ' + ', '.join(model['products']))
    if model['groups']:
        parts.append('channel groups: ' + ', '.join(g['name'] for g in model['groups']))
    for link_product in model['products']:
        lanes = [use['lane'] for use in model['uses'] if use['product'] == link_product]
        if lanes:
            parts.append(f"{link_product} runs on {', '.join(lanes)}")
    return '. '.join(parts) + '.'


def existing_image(section_dir):
    for fmt in IMAGE_FORMATS:
        candidate = section_dir / 'media' / f'{IMAGE_STEM}.{fmt}'
        if image_exists(candidate):
            return candidate
    return None


def run_generation(args, api_key):
    domain_id, domain_dir = project_paths.domain_selection(args.domain, args.domain_dir)
    project = project_paths.resolve_project_root(args.project, domain_dir)
    project_paths.configure(project)
    files = list_domain_files(f'{SECTION}/deployment.json', domain_dir.name if domain_dir else domain_id,
                              project_paths.DOMAINS_ROOT)
    if not files:
        print('No domains with a deployment model found for the selected scope.')
        return 0
    prepared = []
    for deployment_path in files:
        section_dir = deployment_path.parent
        model = collect_model(section_dir.parent)
        if not (model['products'] and model['uses']):
            print(f'Skip (no products deployed to channels yet): {section_dir.parent.name}')
            continue
        prepared.append((section_dir, model, build_prompt(model, args.scene, args.aspect_ratio)))
    needs_api = any(args.overwrite or not existing_image(section_dir) for section_dir, _, _ in prepared)
    if needs_api and not (args.dry_run or api_key):
        raise ValueError(f'Set {args.api_key_env} locally, or use --dry-run.')

    generated = 0
    for section_dir, model, prompt in prepared:
        current = existing_image(section_dir)
        should_generate = (args.overwrite or not current) and (not args.limit or generated < args.limit)
        target = section_dir / 'media' / f'{IMAGE_STEM}.png'
        action = 'Generate' if should_generate else ('Reuse' if current else 'Skip (limit reached)')
        print(f'{action}: {section_dir.parent.name}\n  {current or target}', flush=True)
        if args.show_prompts:
            print(prompt, flush=True)
        if not should_generate:
            continue
        if not args.dry_run:
            image = call_gemini_nanobanana_api(api_key, SimpleNamespace(prompt=prompt), args)
            image_bytes, output_format = overview.shrink_image(image.image_bytes, args.max_width) or (
                image.image_bytes, image.output_format)
            path = target.with_suffix(f'.{output_format}')
            write_bytes(path, image_bytes)
            for fmt in IMAGE_FORMATS:  # Keep exactly one deployment image per domain.
                stale = path.with_suffix(f'.{fmt}')
                if stale != path and stale.exists():
                    stale.unlink()
            write_bytes(path.with_name(f'{IMAGE_STEM}.prompt.txt'), (prompt + '\n').encode('utf-8'))
            write_bytes(path.with_name(f'{IMAGE_STEM}.alt.txt'), (deployment_alt(model) + '\n').encode('utf-8'))
            print(f'  Saved: {path}', flush=True)
        generated += 1
    verb = 'Would generate' if args.dry_run else 'Generated'
    print(f'{verb} {generated} deployment overview image(s). Rebuild the products section to show them.')
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
