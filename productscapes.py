#!/usr/bin/env python3
"""Create and build Productscapes with Python 3.10+ and its standard library."""
import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

TOOLKIT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLKIT / '_wiring'))
from domain_paths import discover_domain_dirs, resolve_domain_dir

SECTIONS = ('start', 'customers', 'products', 'product-bricks', 'teams', 'competition', 'residuality')
REQUIRED = (
    'start/config.json', 'customers/customers.json', 'customers/insights.json',
    'customers/links.json', 'product-deployments/products.json',
    'product-deployments/deployment.json', 'product-bricks/product-bricks.json',
    'product-bricks/product-stream.json', 'teams/teams.json',
    'data/data-assets.json', 'business/competition.json',
)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def revision():
    result = subprocess.run(['git', '-C', str(TOOLKIT), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if result.returncode or Path(result.stdout.strip()).resolve() != TOOLKIT:
        return None
    return subprocess.check_output(['git', '-C', str(TOOLKIT), 'rev-parse', 'HEAD'], text=True).strip()


def run_script(relative, arguments, project, quiet=False):
    env = dict(os.environ, PRODUCTSCAPES_PROJECT=str(project), PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    result = subprocess.run([sys.executable, str(TOOLKIT / relative), *arguments], cwd=project,
                            env=env, capture_output=quiet, text=True)
    if result.returncode:
        if quiet:
            sys.stderr.write(result.stdout + result.stderr)
        raise RuntimeError(f'{relative} failed (exit {result.returncode}).')


def selected_domains(args):
    root = args.project / '_config/product-domains'
    if args.domain:
        return [resolve_domain_dir(args.domain, domains_root=root)]
    if not args.all:
        raise ValueError('Choose a domain ID or pass --all.')
    domains = [p for p in discover_domain_dirs(root) if (p / 'start/config.json').is_file()]
    if not domains:
        raise ValueError('No registered domains. Create one with: python3 productscapes.py new <id> --group <group>')
    return domains


def preflight(domains, *, require_artifacts=True):
    """Check inputs before generators replace any previously built pages."""
    for domain in domains:
        if require_artifacts:
            missing = [name for name in REQUIRED if not (domain / name).is_file()]
            if missing:
                raise ValueError(f'{domain.name}: missing required sources: {", ".join(missing)}')
        for path in domain.rglob('*.json'):
            read_json(path)
        config = read_json(domain / 'start/config.json')
        # Folder IDs are authoritative, as in the original generators. Some
        # imported examples retain an older ID in their display metadata.
        for field in ('name', 'description'):
            if not isinstance(config.get(field), str) or not config[field].strip():
                raise ValueError(f'{domain.name}: start/config.json needs a nonempty {field}.')


def init_project(project):
    project.mkdir(parents=True, exist_ok=True)
    if project == TOOLKIT:
        return
    config = project / 'productscapes.json'
    launcher = project / 'productscapes.py'
    if not config.exists():
        write_json(config, {'toolkit': os.path.relpath(TOOLKIT, project), 'revision': revision()})
    if not launcher.exists():
        shutil.copy2(TOOLKIT / 'project-template/productscapes.py', launcher)
    for name in ('AGENTS.md', '.gitignore'):
        if not (project / name).exists():
            shutil.copy2(TOOLKIT / 'project-template' / name, project / name)


def new_domain(args):
    for label, value in (('domain ID', args.domain), ('group', args.group)):
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value) or value == 'start':
            raise ValueError(f'{label} must be a lowercase slug; "start" is reserved for navigation.')
    domains_root = args.project / '_config/product-domains'
    if any(p.name == args.domain for p in discover_domain_dirs(domains_root)):
        raise ValueError(f'Domain ID {args.domain!r} already exists. IDs are unique across groups.')
    destination = domains_root / args.group / args.domain
    if destination.exists():
        raise ValueError(f'Refusing to overwrite {destination}.')
    name = args.name or args.domain.replace('-', ' ').title()
    description = args.description or f'{name}: an unauthored product-domain scaffold.'
    replacements = {'__DOMAIN_ID__': args.domain, '__DOMAIN_NAME__': name, '__DOMAIN_DESCRIPTION__': description}

    def substitute(value):
        if isinstance(value, str):
            return replacements.get(value, value)
        if isinstance(value, list):
            return [substitute(item) for item in value]
        if isinstance(value, dict):
            return {key: substitute(item) for key, item in value.items()}
        return value

    init_project(args.project)
    for source in (TOOLKIT / '_templates/domain').rglob('*'):
        if source.is_file():
            target = destination / source.relative_to(TOOLKIT / '_templates/domain')
            if source.suffix == '.json':
                write_json(target, substitute(read_json(source)))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                content = source.read_text(encoding='utf-8')
                for token, replacement in replacements.items():
                    content = content.replace(token, replacement)
                target.write_text(content, encoding='utf-8')
    print(f'Created {destination}\nThe scaffold has empty collections. Author the domain using skills/new-product-domain/SKILL.md.')


def build(args):
    domains = selected_domains(args)
    preflight(domains)
    docs = args.project / 'docs'
    if docs.is_symlink():
        raise ValueError('The docs output directory must not be a symlink.')
    for domain in domains:
        target = docs / domain.parent.name / domain.name
        if not target.resolve().is_relative_to(docs.resolve()):
            raise ValueError(f'Output resolves outside docs/: {target}')
    failures = []
    for domain in domains:
        config = read_json(domain / 'start/config.json')
        arguments = [domain.name, config['name'], config['description']]
        domain_failed = False
        for section in args.sections or SECTIONS:
            try:
                run_script(f'_wiring/product-domains/generate-{section}-docs.py', arguments, args.project, quiet=not args.verbose)
            except RuntimeError as error:
                failures.append(f'{domain.name}/{section}')
                domain_failed = True
                print(str(error), file=sys.stderr)
        if not domain_failed:
            print(f'Built {domain.parent.name}/{domain.name}', flush=True)
    run_script('_wiring/evidence-explorer/generate-evidence-explorer-docs.py', [], args.project, quiet=not args.verbose)
    if (args.project / '_config/start-packages').is_dir():
        run_script('_wiring/generate-start-apps-docs.py', [], args.project, quiet=not args.verbose)
    build_index(args.project)
    if failures:
        raise RuntimeError(f'Build finished with {len(failures)} failure(s): {", ".join(failures)}')
    print(f'Site: {docs / "index.html"}')


def build_index(project):
    groups = {}
    for domain in discover_domain_dirs(project / '_config/product-domains'):
        page = Path(domain.parent.name) / domain.name / 'start/index.html'
        if not (project / 'docs' / page).is_file():
            continue
        config = read_json(domain / 'start/config.json')
        groups.setdefault(domain.parent.name, []).append(
            '<li><a href="' + html.escape(page.as_posix(), quote=True) + '">' +
            html.escape(config['name']) + '</a><p>' + html.escape(config['description']) + '</p></li>')
    content = '\n'.join('<section><h2>' + html.escape(group.replace('-', ' ').title()) +
                        '</h2><ul>' + '\n'.join(cards) + '</ul></section>' for group, cards in sorted(groups.items()))
    template = (TOOLKIT / '_templates/catalog/index.html').read_text(encoding='utf-8')
    (project / 'docs/index.html').write_text(template.replace('${domains}', content), encoding='utf-8')
    (project / 'docs/.nojekyll').touch()


def validate(args):
    domains = selected_domains(args)
    preflight(domains)
    arguments = [p.name for p in domains] + (['--strict-ids'] if args.strict_ids else [])
    run_script('skills/scripts/validate-domain-model.py', arguments, args.project)


def install_skills(args):
    """Copy the portable instructions and shared references, keeping scripts in the toolkit."""
    destination = args.project / args.target
    sources = [p for p in sorted((TOOLKIT / 'skills').iterdir())
               if p.is_dir() and ((p / 'SKILL.md').is_file() or p.name == '_references')]
    conflicts = [p.name for p in sources if (destination / p.name).exists()]
    if conflicts and not args.update:
        raise ValueError(f'Skills already exist in {destination}: {", ".join(conflicts)}. Use --update to refresh them.')
    for source in sources:
        shutil.copytree(source, destination / source.name, dirs_exist_ok=args.update)
    print(f'Installed {len(sources) - 1} skills in {destination}')


def images(args):
    resolve_domain_dir(args.domain, domains_root=args.project / '_config/product-domains')
    scripts = {
        'jtbd': 'generate_jtbd_images_gemini_nanobanana_api.py',
        'journey': 'generate_journey_images_gemini_nanobanana_api.py',
        'relations': 'generate_customer_relations_images_gemini_nanobanana_api.py',
        'residuality': 'generate_residuality_images_gemini_nanobanana_api.py',
        'icons': 'generate_missing_domain_icons_gemini_nanobanana_api.py',
    }
    for kind in scripts if args.kind == 'all' else [args.kind]:
        extra = ['--domain', args.domain]
        if args.dry_run:
            extra.append('--dry-run')
        if args.lightweight and kind in ('jtbd', 'journey'):
            extra.append('--lightweight')
        if args.skip_existing:
            extra.append('--skip-existing')
        run_script('_config/scripts/image-generation/' + scripts[kind], extra, args.project)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version='productscapes 0.1.0')
    commands = parser.add_subparsers(dest='command', required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--project', type=Path, default=Path(os.environ.get('PRODUCTSCAPES_PROJECT', Path.cwd())),
                        help='Data project root (default: current directory).')
    new = commands.add_parser('new', parents=[common], help='Create an empty, buildable domain scaffold.')
    new.add_argument('domain')
    new.add_argument('--group', required=True)
    new.add_argument('--name')
    new.add_argument('--description')
    new.set_defaults(action=new_domain)
    for command, action in (('build', build), ('validate', validate)):
        command_parser = commands.add_parser(command, parents=[common])
        selection = command_parser.add_mutually_exclusive_group()
        selection.add_argument('domain', nargs='?')
        selection.add_argument('--all', action='store_true')
        command_parser.set_defaults(action=action)
        if command == 'build':
            command_parser.add_argument('--sections', nargs='+', choices=SECTIONS)
            command_parser.add_argument('--verbose', action='store_true')
        else:
            command_parser.add_argument('--strict-ids', action='store_true')
    listing = commands.add_parser('list', parents=[common], help='List registered domains with their groups.')
    listing.set_defaults(action=lambda args: [print(f'{p.parent.name}/{p.name}') for p in
        discover_domain_dirs(args.project / '_config/product-domains') if (p / 'start/config.json').is_file()])
    info = commands.add_parser('info', parents=[common], help='Show toolkit and project paths.')
    info.set_defaults(action=lambda args: print(json.dumps({'toolkit': str(TOOLKIT), 'project': str(args.project),
        'schemas': str(TOOLKIT / '_config/_schema'), 'skills': str(TOOLKIT / 'skills'), 'revision': revision()}, indent=2)))
    skills = commands.add_parser('skills', parents=[common], help='Install portable skills into this project.')
    skills.add_argument('--target', default='.agents/skills', help='Skill directory, e.g. .agents/skills or .claude/skills.')
    skills.add_argument('--update', action='store_true', help='Refresh existing installed skills.')
    skills.set_defaults(action=install_skills)
    kpis = commands.add_parser('check-kpis', parents=[common])
    kpis.add_argument('domain')
    kpis.set_defaults(action=lambda args: run_script('skills/scripts/check-kpi-pyramids.py', [args.domain], args.project))
    media = commands.add_parser('images', parents=[common], help='Optional Gemini image generation (requires credentials).')
    media.add_argument('domain')
    media.add_argument('--kind', choices=('jtbd', 'journey', 'relations', 'residuality', 'icons', 'all'), default='all')
    media.add_argument('--dry-run', action='store_true')
    media.add_argument('--lightweight', action='store_true')
    media.add_argument('--skip-existing', action='store_true')
    media.set_defaults(action=images)
    args = parser.parse_args()
    args.project = args.project.expanduser().resolve()
    try:
        args.action(args)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f'Error: {error}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
