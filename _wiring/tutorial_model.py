"""The tutorial contract shared by domain validation and page generation."""
from datetime import date
from functools import lru_cache
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

TOOLKIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLKIT / 'skills/scripts'))
import schema_check


@lru_cache(maxsize=1)
def tutorial_schema():
    return json.loads((TOOLKIT / '_config/_schema/tutorial.schema.json').read_text(encoding='utf-8'))


def tutorial_media_groups(payload):
    """Yield containers that support illustrations, in reading order."""
    if 'participantsOverview' in payload:
        yield '$.participantsOverview', payload['participantsOverview']
    for index, concept in enumerate(payload.get('concepts', [])):
        yield f'$.concepts[{index}]', concept
    if 'walkthrough' in payload:
        yield '$.walkthrough', payload['walkthrough']


def tutorial_images(payload):
    """Yield image locations and entries in reading order."""
    for path, container in tutorial_media_groups(payload):
        for index, media in enumerate(container.get('media', [])):
            yield f'{path}.media[{index}]', media


def tutorial_image_path(tutorial_dir, src):
    """Resolve a portable local image path without leaving the tutorial folder."""
    if not re.fullmatch(tutorial_schema()['$defs']['image']['properties']['src']['pattern'], src):
        raise ValueError('must be a PNG, JPEG, or WebP path under media/ using letters, digits, hyphens, or underscores')
    if tutorial_dir is None:
        return Path(src)  # Shape-only validation must not depend on the caller's working directory.
    root = Path(tutorial_dir).resolve()
    target = root / src
    if not target.resolve().is_relative_to(root):
        raise ValueError('image path resolves outside the tutorial folder')
    return target


def validate_tutorial(payload, domain_id, tutorial_dir=None):
    """Return actionable errors; incomplete drafts are valid, empty ready pages aren't."""
    schema = tutorial_schema()
    errors = schema_check.validate(payload, schema)
    if errors:
        return errors
    # The shared checker implements a small schema subset. Apply this contract's
    # ready-state conditional explicitly, reusing its required/minItems rules.
    if payload['status'] == 'ready':
        schema_check.validate(payload, schema['then'], root_schema=schema, errors=errors)
    if payload['domainId'] != domain_id:
        errors.append(f'$.domainId: must match the domain folder {domain_id!r}')
    if 'updated' in payload:
        try:
            date.fromisoformat(payload['updated'])
        except ValueError:
            errors.append('$.updated: must be a real date in YYYY-MM-DD form')
    links = [(f'$.history[{i}].sourceUrl', item['sourceUrl'])
             for i, item in enumerate(payload.get('history', [])) if 'sourceUrl' in item]
    links += [(f'$.furtherReading[{i}].url', item['url'])
              for i, item in enumerate(payload.get('furtherReading', []))]
    for path, url in links:
        try:
            parsed = urlsplit(url)
            valid = (parsed.scheme in ('http', 'https') and parsed.hostname and
                     not parsed.username and not parsed.password and
                     not any(ord(character) < 32 for character in url))
            parsed.port  # Validate a supplied port too.
        except ValueError:
            valid = False
        if not valid:
            errors.append(f'{path}: must be an absolute HTTP(S) URL without credentials')
    if payload.get('participantsOverview') and not payload.get('participants'):
        errors.append('$.participantsOverview: needs participants to explain')
    for path, container in tutorial_media_groups(payload):
        ids = [media['id'] for media in container.get('media', []) if 'id' in media]
        if len(ids) != len(set(ids)):
            errors.append(f'{path}.media: image ids must be unique within this entry')
    for path, media in tutorial_images(payload):
        try:
            image = tutorial_image_path(tutorial_dir, media['src'])
            if tutorial_dir is not None and (not image.is_file() or image.stat().st_size == 0):
                errors.append(f'{path}.src: image is missing or empty: {media["src"]}')
        except (OSError, ValueError) as error:
            errors.append(f'{path}.src: {error}')
    return errors
