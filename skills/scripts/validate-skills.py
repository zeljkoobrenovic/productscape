#!/usr/bin/env python3
"""Validate the portable skill bundle without third-party packages."""
import re
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    files = sorted(root.glob('*/SKILL.md'))
    errors = []
    names = set()
    if not files:
        errors.append('No skills found.')
    for path in files:
        text = path.read_text(encoding='utf-8')
        parts = text.split('---\n', 2)
        if len(parts) != 3 or parts[0]:
            errors.append(f'{path}: missing YAML frontmatter')
            continue
        fields = {}
        for line in parts[1].splitlines():
            if ':' in line and not line.startswith(' '):
                key, value = line.split(':', 1)
                fields[key] = value.strip().strip('"').strip("'")
        name = fields.get('name', '')
        if not re.fullmatch(r'[a-z0-9-]{1,64}', name) or name != path.parent.name:
            errors.append(f'{path}: invalid name')
        if name in names:
            errors.append(f'{path}: duplicate name {name}')
        names.add(name)
        if not fields.get('description'):
            errors.append(f'{path}: missing description')
        for link in re.findall(r'\]\(([^)]+)\)', parts[2]):
            if '://' in link or link.startswith('#'):
                continue
            target = link.split('#', 1)[0]
            if target and not (path.parent / target).exists():
                errors.append(f'{path}: broken reference {link}')
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print(f'Skill validation passed: {len(files)} skills.')
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
