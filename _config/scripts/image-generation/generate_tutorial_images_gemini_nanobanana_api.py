#!/usr/bin/env python3
"""Illustrate tutorial concepts and overviews, checkpoint media, and retain prompts.

Run from the data project, use --project, or select a complete --domain-dir.
Images belong in tutorial/media; the tutorial renderer copies referenced assets
into docs. Existing images are reused by default. No API is used for --dry-run
or --json-only, and ordinary builds never invoke this script.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TOOLKIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TOOLKIT / '_wiring'))
import project_paths
from domain_paths import list_domain_files
from tutorial_model import tutorial_image_path, validate_tutorial

# Reuse the existing generator's format handling and atomic file writes.
from generate_customer_icons_gemini_nanobanana_api import (
    GeneratedImage, IMAGE_FORMATS, extract_generated_image, image_exists, write_bytes,
)

DEFAULT_MODEL = 'gemini-3-pro-image-preview'
MEDIA_ID = 'concept-illustration'


@dataclass
class IllustrationTarget:
    content: dict
    key: str
    image_path: Path
    prompt: str
    media_id: str
    title: str
    alt: str
    caption: str
    parent: dict | None = None
    parent_key: str | None = None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--domain', help='Domain ID or domain folder; omit to process all tutorials.')
    scope.add_argument('--domain-dir', type=Path, help='Full domain folder; also selects the data project.')
    parser.add_argument('--project', type=Path, help='Data project root (default: current project).')
    parser.add_argument('--section', choices=('all', 'concepts', 'participants', 'walkthrough'), default='all',
                        help='Default: concepts and configured overviews. Select one overview to create it directly.')
    parser.add_argument('--concept', help='One exact concept term or its filename key, shown by --dry-run.')
    parser.add_argument('--limit', type=int, default=0, help='Maximum new images across the selected scope; 0 means all.')
    parser.add_argument('--model', default=DEFAULT_MODEL, help='Gemini image model, matching the other repository scripts by default.')
    parser.add_argument('--aspect-ratio', choices=('16:9', '3:2', '4:3', '1:1'), default='16:9')
    parser.add_argument('--image-size', choices=('1K', '2K', '4K'), default='1K')
    parser.add_argument('--dry-run', action='store_true', help='Print actions without writes or API calls.')
    parser.add_argument('--show-prompts', action='store_true', help='Include complete prompts in the output.')
    parser.add_argument('--json-only', action='store_true', help='Link existing images only; call no API.')
    existing = parser.add_mutually_exclusive_group()
    existing.add_argument('--skip-existing', action='store_true', help='Reuse existing images (the default).')
    existing.add_argument('--overwrite', action='store_true', help='Regenerate selected concept illustrations.')
    parser.add_argument('--api-key-env', choices=('GEMINI_API_KEY', 'GOOGLE_API_KEY'), default='GEMINI_API_KEY')
    parser.add_argument('--max-retries', type=int, default=4)
    parser.add_argument('--retry-delay-seconds', type=float, default=5.0)
    parser.add_argument('--sleep-seconds', type=float, default=0.0)
    args = parser.parse_args(argv)
    for name in ('limit', 'max_retries', 'retry_delay_seconds', 'sleep_seconds'):
        if not math.isfinite(getattr(args, name)) or getattr(args, name) < 0:
            parser.error(f'--{name.replace("_", "-")} must be finite and nonnegative')
    if args.json_only and args.overwrite:
        parser.error('--json-only cannot regenerate images with --overwrite')
    if args.concept and args.section not in ('all', 'concepts'):
        parser.error('--concept requires --section concepts or all')
    return args


def concept_key(term):
    """Use the term, not its array position, so reordering keeps existing images."""
    key = re.sub(r'[^a-z0-9]+', '-', term.lower()).strip('-')[:100].rstrip('-')
    if not key:
        raise ValueError(f'Concept needs a term that can form a filename: {term!r}')
    return key


def build_concept_prompt(tutorial, concept, aspect_ratio='16:9'):
    context = (f"Meaning: {concept['meaning']}\nConcrete example: {concept['example']}\n"
               f"Why this matters: {concept['whyItMatters']}")
    scene = concept.get('illustrationPrompt') or (
        'Turn the concrete example into a simple visual explanation. Show the essential relationship or distinction, '
        'using recognizable people and objects. Choose one scene or two to three clearly separated panels only when comparison needs them.')
    return build_prompt(tutorial, concept['term'], context, scene, aspect_ratio)


def build_prompt(tutorial, subject, context, scene, aspect_ratio):
    return f'''Use case: scientific-educational
Asset type: one illustration in a plain-language product-domain tutorial for adults.
Domain: {tutorial['title']}
Reader: {tutorial.get('audience', 'A capable adult coming from a completely different field.')}
Scope: {tutorial.get('scope', '')}
Subject: {subject}
{context}

Teaching scene:
{scene}

Style and composition:
- Aspect ratio {aspect_ratio}, generous margins, bright warm-white background.
- A polished adult educational illustration: flat editorial drawing, crisp navy outlines,
  restrained teal, blue, and warm amber accents, subtle texture, very little shading.
- Make the concept understandable at the width of a reading column and on a phone.
- Use a small number of recognizable objects and people. Keep relationships spatially clear.
- Use an inclusive cast without occupational or cultural stereotypes.
- Short everyday labels are welcome where they teach the distinction. Use only labels
  explicitly requested in the teaching scene; otherwise keep the image free of text.
- Arrows must have a clear meaning and direction; do not connect unrelated comparison
  panels as though they are required stages. Do not imply certainty, causality, proportions,
  cash movements, or guaranteed outcomes that the explanation does not support.
- Keep all important content inside the frame. No headline, watermark, brand logo,
  decorative charts, invented statistics, jargon, tiny writing, photorealism, or 3D rendering.
- Explain the idea visually. The surrounding tutorial provides its full definition and caveats.
'''.strip()


def build_targets_for_file(path, payload, concept_filter=None, aspect_ratio='16:9', section='all'):
    domain = path.parents[1]
    if not path.resolve().is_relative_to(domain.resolve()):
        raise ValueError(f'Tutorial source resolves outside the selected domain: {path}')
    errors = validate_tutorial(payload, domain.name)
    if errors:
        raise ValueError(f'{path}:\n' + '\n'.join(errors))
    targets, keys = [], set()

    def add(content, key, filename, media_id, title, alt, caption, prompt, parent=None, parent_key=None):
        candidate = tutorial_image_path(path.parent, f'media/{filename}.png')
        candidates = [candidate.with_suffix(f'.{fmt}') for fmt in IMAGE_FORMATS]
        for media in content.get('media', []):
            if media.get('id') == media_id:
                candidates.insert(0, tutorial_image_path(path.parent, media['src']))
        # Recover any supported image saved before an interrupted JSON update.
        for candidate in candidates:
            tutorial_image_path(path.parent, candidate.relative_to(path.parent.resolve()).as_posix())
        image = next((candidate for candidate in candidates if image_exists(candidate)), candidates[0])
        targets.append(IllustrationTarget(content, key, image, prompt, media_id, title, alt, caption, parent, parent_key))

    concepts = payload.get('concepts', []) if section in ('all', 'concepts') else []
    for concept in concepts:
        key = concept_key(concept['term'])
        if key in keys:
            raise ValueError(f'Concept terms produce the same filename key {key!r} in {path}; use distinct terms.')
        keys.add(key)
        if concept_filter and concept_filter not in (concept['term'], key):
            continue
        add(concept, key, f'concept-{key}', MEDIA_ID, concept['term'],
            f"{concept['term']}: {concept['example']}", concept['whyItMatters'],
            build_concept_prompt(payload, concept, aspect_ratio))
    if concept_filter:
        return targets  # A concept selection never expands into section overviews.

    case = payload.get('walkthrough')
    if section in ('all', 'walkthrough') and case and (
            section == 'walkthrough' or case.get('illustrationPrompt') or case.get('media')):
        context = 'Setup: ' + case['setup'] + '\n' + '\n'.join(
            f"Step {i}: {step['title']}. {step['whatHappens']} Why: {step['whyItMatters']} "
            f"Possible complication: {step.get('watchOut', 'None specified.')}"
            for i, step in enumerate(case['steps'], 1)) + '\nOutcome: ' + case['outcome']
        scene = case.get('illustrationPrompt') or (
            'Show the existing walkthrough as a short story in reading order, with a consistent cast. '
            'Use each step title as its label. Include a complication from the text. '
            'Keep hypothetical outcomes visibly conditional, and do not combine alternative cases into a single sequence.')
        add(case, 'walkthrough-overview', 'walkthrough-overview', 'walkthrough-overview', case['title'],
            'Walkthrough: ' + '; '.join(step['title'] for step in case['steps']) + '.', case['outcome'],
            build_prompt(payload, case['title'], context, scene, aspect_ratio))

    overview = payload.get('participantsOverview', {})
    if section in ('all', 'participants') and payload.get('participants') and (
            section == 'participants' or overview.get('illustrationPrompt') or overview.get('media')):
        context = '\n'.join(f"{person['name']}: {person['role']} Cares about: {person['caresAbout']}"
                            for person in payload['participants'])
        scene = overview.get('illustrationPrompt') or (
            'Map the participants and their relationships. Label people with their names from the source. '
            'Distinguish funding, ownership, management, and everyday work. '
            'Use short plain-language relationship labels justified by the roles. Include affected people, not just decision makers.')
        add(overview, 'participants-overview', 'participants-overview', 'participants-overview',
            'The people involved', 'Participant map: ' + '; '.join(person['name'] for person in payload['participants']) + '.',
            'Different people provide resources, make decisions, do the work, and experience the consequences.',
            build_prompt(payload, 'The people involved and how they relate', context, scene, aspect_ratio),
            payload, 'participantsOverview')
    return targets


def call_gemini_nanobanana_api(api_key, target, args):
    url = ('https://generativelanguage.googleapis.com/v1beta/models/' +
           urllib.parse.quote(args.model, safe='') + ':generateContent')
    body = json.dumps({
        'contents': [{'parts': [{'text': target.prompt}]}],
        'generationConfig': {
            'responseModalities': ['IMAGE'],
            'imageConfig': {'aspectRatio': args.aspect_ratio, 'imageSize': args.image_size},
        },
    }).encode('utf-8')
    attempts = args.max_retries + 1

    def redacted(detail):
        return str(detail).replace(api_key, '[redacted]').replace(urllib.parse.quote(api_key, safe=''), '[redacted]')

    for attempt in range(attempts):
        request = urllib.request.Request(url, data=body, method='POST', headers={
            'Content-Type': 'application/json', 'x-goog-api-key': api_key,
        })
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return extract_generated_image(json.loads(response.read().decode('utf-8')))
        except urllib.error.HTTPError as error:
            detail = redacted(error.read().decode('utf-8', errors='replace'))
            if error.code not in (429, 500, 502, 503, 504) or attempt + 1 == attempts:
                raise RuntimeError(f'Gemini API error {error.code}: {detail}') from None
        except (urllib.error.URLError, ConnectionError, TimeoutError) as error:
            if attempt + 1 == attempts:
                raise RuntimeError(f'Network error calling Gemini: {redacted(error)}') from None
        delay = min(60.0, args.retry_delay_seconds * 2 ** attempt)
        print(f'Transient Gemini failure; retry {attempt + 1}/{args.max_retries} in {delay:g}s.', flush=True)
        time.sleep(delay)
    raise RuntimeError('Gemini request failed.')


def link_image(target, tutorial_dir):
    """Update our own media entry, preserving other images and reviewed captions."""
    items = target.content.setdefault('media', [])
    current = next((item for item in items if item.get('id') == target.media_id), None)
    replacement = dict(current or {})
    replacement.update(id=target.media_id, type='image', src=target.image_path.relative_to(tutorial_dir.resolve()).as_posix())
    replacement.setdefault('title', target.title)
    replacement.setdefault('alt', target.alt)
    replacement.setdefault('caption', target.caption)
    if current == replacement:
        return False
    if current is None:
        items.append(replacement)
    else:
        items[items.index(current)] = replacement
    if target.parent is not None:
        target.parent[target.parent_key] = target.content
    return True


def run_generation(args, api_key):
    domain_id, domain_dir = project_paths.domain_selection(args.domain, args.domain_dir)
    project = project_paths.resolve_project_root(args.project, domain_dir)
    project_paths.configure(project)
    files = list_domain_files('tutorial/tutorial.json', domain_dir.name if domain_dir else domain_id,
                              project_paths.DOMAINS_ROOT)
    # Validate the entire selected scope before any API calls or source edits.
    prepared = []
    for path in files:
        original = path.read_bytes()
        payload = json.loads(original)
        targets = build_targets_for_file(path, payload, args.concept, args.aspect_ratio, args.section)
        prepared.append((path, original, payload, targets))
    if args.concept and not any(targets for _, _, _, targets in prepared):
        raise ValueError(f'No concept matches {args.concept!r}. Use --dry-run to list concept keys.')
    if not any(targets for _, _, _, targets in prepared):
        print('No tutorial illustrations found for the selected scope. Nothing to illustrate.')
        return 0
    needs_api = any(args.overwrite or not image_exists(target.image_path)
                    for _, _, _, targets in prepared for target in targets)
    if needs_api and not (args.dry_run or args.json_only or api_key):
        raise ValueError(f'Set {args.api_key_env} locally, or use --dry-run or --json-only.')

    generated, updates = 0, 0
    for path, original, payload, targets in prepared:
        changed_file = False
        for target in targets:
            should_generate = (not args.json_only and (not args.limit or generated < args.limit)
                               and (args.overwrite or not image_exists(target.image_path)))
            action = 'Generate' if should_generate else ('Reuse' if image_exists(target.image_path) else 'Skip missing')
            print(f'{action}: {target.key}\n  {target.image_path}', flush=True)
            if args.show_prompts:
                print(target.prompt, flush=True)
            if should_generate:
                if not args.dry_run:
                    image = call_gemini_nanobanana_api(api_key, target, args)
                    target.image_path = target.image_path.with_suffix(f'.{image.output_format}')
                    tutorial_image_path(path.parent, target.image_path.relative_to(path.parent.resolve()).as_posix())
                    write_bytes(target.image_path, image.image_bytes)
                    prompt_path = target.image_path.with_suffix('.prompt.txt')
                    if not prompt_path.resolve().is_relative_to(path.parent.resolve()):
                        raise ValueError(f'Prompt path resolves outside the tutorial: {prompt_path}')
                    write_bytes(prompt_path, (target.prompt + '\n').encode('utf-8'))
                generated += 1
            if image_exists(target.image_path) and not args.dry_run and link_image(target, path.parent):
                if path.read_bytes() != original:
                    raise RuntimeError(f'Tutorial changed during generation; saved the image but kept the newer JSON: {path}. Rerun to link it.')
                original = (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
                write_bytes(path, original)
                changed_file = True
            if should_generate and args.sleep_seconds and not args.dry_run:
                time.sleep(args.sleep_seconds)
        updates += int(changed_file)
    verb = 'Would generate' if args.dry_run else 'Generated'
    print(f'{verb} {generated} tutorial illustration(s). Updated {updates} tutorial JSON file(s).')
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
