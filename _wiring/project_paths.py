"""Separate toolkit resources from the project being authored or built.

The CLI passes PRODUCTSCAPES_PROJECT to subprocesses. Direct generator calls
default to the toolkit checkout, preserving the original in-repository workflow.
"""
import os
from pathlib import Path

TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.environ.get('PRODUCTSCAPES_PROJECT', TOOLKIT_ROOT)).expanduser().resolve()
DOMAINS_ROOT = PROJECT_ROOT / '_config' / 'product-domains'
TEMPLATES_ROOT = TOOLKIT_ROOT / '_templates'
DOCS_ROOT = PROJECT_ROOT / 'docs'


def template_path(section):
    """Existing renderers concatenate filenames, so retain a trailing slash."""
    return str(TEMPLATES_ROOT / section) + '/'


def navigation_path():
    override = DOMAINS_ROOT / 'start' / 'apps.json'
    return override if override.is_file() else TOOLKIT_ROOT / '_config/product-domains/start/apps.json'
