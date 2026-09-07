#!/usr/bin/env python3
"""Use the Productscapes toolkit pinned by this data repository."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent


def main():
    config = json.loads((PROJECT / 'productscapes.json').read_text(encoding='utf-8'))
    override = os.environ.get('PRODUCTSCAPES_HOME')
    toolkit = Path(override or config.get('toolkit', '../productscape')).expanduser()
    if not toolkit.is_absolute():
        toolkit = PROJECT / toolkit
    toolkit = toolkit.resolve()
    entry = toolkit / 'productscapes.py'
    if not entry.is_file() or not (toolkit / '_wiring/project_paths.py').is_file():
        raise ValueError(f'Productscapes toolkit not found at {toolkit}. Clone productscape beside this repository, '
                         'or set PRODUCTSCAPES_HOME to its checkout path.')
    if entry == Path(__file__).resolve():
        raise ValueError('The toolkit path points to this project, not the productscapes toolkit.')
    expected = config.get('revision')
    if expected and not os.environ.get('PRODUCTSCAPES_ALLOW_UNPINNED'):
        result = subprocess.run(['git', '-C', str(toolkit), 'rev-parse', 'HEAD'], capture_output=True, text=True)
        if result.returncode or result.stdout.strip() != expected:
            raise ValueError(f'This project requires productscapes commit {expected}. Run git -C "{toolkit}" checkout {expected}, '
                             'or set PRODUCTSCAPES_ALLOW_UNPINNED=1 for toolkit development.')
    os.environ['PRODUCTSCAPES_PROJECT'] = str(PROJECT)
    runpy.run_path(str(entry), run_name='__main__')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        sys.exit(f'Error: {error}')
