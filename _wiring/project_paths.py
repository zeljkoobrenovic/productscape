"""Separate toolkit resources from the project being authored or built.

The CLI passes resolved project and render paths to subprocesses. Domain page
generators can configure these paths from their own command-line arguments.
Other direct generators retain the toolkit checkout as their default project.
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
    if NAVIGATION_FILE is not None:
        return NAVIGATION_FILE
    override = DOMAINS_ROOT / 'start' / 'apps.json'
    return override if override.is_file() else TOOLKIT_ROOT / '_config/product-domains/start/apps.json'


def add_render_arguments(parser):
    parser.add_argument('--output-dir', type=Path,
                        help='Site output root (default: <project>/docs); keeps <group>/<domain>/<section> paths.')
    parser.add_argument('--templates-dir', type=Path,
                        help='Template root containing section folders and _imports (default: toolkit _templates).')
    parser.add_argument('--navigation-file', type=Path,
                        help='Domain navigation apps.json (default: project navigation, then toolkit navigation).')
    parser.add_argument('--shared-config-dir', type=Path,
                        help='Shared model JSON directory (default: toolkit _config/_shared).')


def domain_selection(domain=None, domain_dir=None):
    """Accept an ID or a folder path without interpreting it after a chdir."""
    if domain and domain_dir:
        raise ValueError('Choose a domain ID/folder or --domain-dir, not both.')
    if domain and (Path(domain).expanduser().is_dir() or '/' in domain):
        domain_dir, domain = Path(domain), None
    if domain_dir is not None:
        domain_dir = Path(domain_dir).expanduser().resolve()
        if not domain_dir.is_dir():
            raise ValueError(f'Domain folder does not exist: {domain_dir}')
        if len(domain_dir.parents) < 4 or domain_dir.parents[1].name != 'product-domains' or domain_dir.parents[2].name != '_config':
            raise ValueError(f'Expected <project>/_config/product-domains/<group>/<domain-id>: {domain_dir}')
    return domain, domain_dir


def resolve_project_root(project=None, domain_dir=None):
    if domain_dir is not None:
        inferred = domain_dir.parents[3]
        if project is not None and Path(project).expanduser().resolve() != inferred:
            raise ValueError(f'--project does not contain the selected domain folder: {domain_dir}')
        return inferred
    return Path(project or os.environ.get('PRODUCTSCAPES_PROJECT', Path.cwd())).expanduser().resolve()


def configure(project, *, output_dir=None, templates_dir=None, navigation_file=None, shared_config_dir=None):
    """Resolve command-line paths before generators change working directory."""
    global PROJECT_ROOT, DOMAINS_ROOT, DOCS_ROOT, TEMPLATES_ROOT, NAVIGATION_FILE, SHARED_CONFIG_ROOT, _OUTPUT_IS_SYMLINK
    PROJECT_ROOT = Path(project).expanduser().resolve()
    DOMAINS_ROOT = PROJECT_ROOT / '_config/product-domains'
    output = Path(output_dir or os.environ.get('PRODUCTSCAPES_OUTPUT', PROJECT_ROOT / 'docs')).expanduser()
    _OUTPUT_IS_SYMLINK = output.is_symlink()
    DOCS_ROOT = output.resolve()
    TEMPLATES_ROOT = Path(templates_dir or os.environ.get('PRODUCTSCAPES_TEMPLATES', TOOLKIT_ROOT / '_templates')).expanduser().resolve()
    SHARED_CONFIG_ROOT = Path(shared_config_dir or os.environ.get('PRODUCTSCAPES_SHARED_CONFIG', TOOLKIT_ROOT / '_config/_shared')).expanduser().resolve()
    navigation = navigation_file or os.environ.get('PRODUCTSCAPES_NAVIGATION')
    NAVIGATION_FILE = Path(navigation).expanduser().resolve() if navigation else None


def render_environment():
    return {
        'PRODUCTSCAPES_OUTPUT': str(DOCS_ROOT),
        'PRODUCTSCAPES_TEMPLATES': str(TEMPLATES_ROOT),
        'PRODUCTSCAPES_NAVIGATION': str(navigation_path()),
        'PRODUCTSCAPES_SHARED_CONFIG': str(SHARED_CONFIG_ROOT),
    }


def validate_render_paths(domains, sections):
    """Check explicit inputs and output boundaries before replacing pages."""
    if _OUTPUT_IS_SYMLINK:
        raise ValueError('The docs output directory must not be a symlink.')
    for folder in (TEMPLATES_ROOT, SHARED_CONFIG_ROOT):
        if not folder.is_dir():
            raise ValueError(f'Input directory does not exist: {folder}')
    if not navigation_path().is_file():
        raise ValueError(f'Navigation file does not exist: {navigation_path()}')
    for section in sections:
        template = TEMPLATES_ROOT / section / 'index.html'
        if not template.is_file():
            raise ValueError(f'Template does not exist: {template}')
    if DOCS_ROOT.exists() and not DOCS_ROOT.is_dir():
        raise ValueError(f'Output is not a directory: {DOCS_ROOT}')
    for source in (PROJECT_ROOT / '_config', PROJECT_ROOT / '_evidence', TEMPLATES_ROOT,
                   SHARED_CONFIG_ROOT, navigation_path(), *domains):
        source = source.resolve()
        if DOCS_ROOT.is_relative_to(source) or source.is_relative_to(DOCS_ROOT):
            raise ValueError(f'Output directory overlaps an input: {DOCS_ROOT} and {source}')
    for domain in domains:
        target = DOCS_ROOT / domain.parent.name / domain.name
        if not target.resolve().is_relative_to(DOCS_ROOT):
            raise ValueError(f'Output resolves outside the output directory: {target}')


configure(PROJECT_ROOT)
