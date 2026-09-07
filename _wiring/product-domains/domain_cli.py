"""Command-line inputs shared by every domain page generator."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import project_paths
from domain_paths import resolve_domain_dir


def load_domain_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('domain', nargs='?', help='Domain folder path, or a domain ID with --project.')
    parser.add_argument('domain_name', nargs='?', help='Legacy display-name override.')
    parser.add_argument('domain_description', nargs='?', help='Legacy description override.')
    parser.add_argument('--domain-dir', type=Path, help='Source domain folder; selects its data project automatically.')
    parser.add_argument('--project', type=Path, help='Data project root for a domain ID.')
    parser.add_argument('--name', help='Display name (default: start/config.json).')
    parser.add_argument('--description', help='Domain description (default: start/config.json).')
    project_paths.add_render_arguments(parser)
    args = parser.parse_args()
    try:
        domain_id, domain_dir = project_paths.domain_selection(args.domain, args.domain_dir)
        if domain_id is None and domain_dir is None:
            raise ValueError('Provide a domain folder or a domain ID with --project.')
        project = project_paths.resolve_project_root(args.project, domain_dir)
        project_paths.configure(
            project, output_dir=args.output_dir, templates_dir=args.templates_dir,
            navigation_file=args.navigation_file, shared_config_dir=args.shared_config_dir,
        )
        domain_dir = resolve_domain_dir(domain_dir.name if domain_dir else domain_id, project_paths.DOMAINS_ROOT)
        config_file = domain_dir / 'start/config.json'
        config = json.loads(config_file.read_text(encoding='utf-8')) if config_file.is_file() else {}
        domain = {
            'id': domain_dir.name,
            'name': args.name if args.name is not None else args.domain_name if args.domain_name is not None else config.get('name'),
            'description': args.description if args.description is not None else args.domain_description if args.domain_description is not None else config.get('description'),
        }
        for field in ('name', 'description'):
            if not isinstance(domain[field], str) or not domain[field].strip():
                raise ValueError(f'Provide --{field} or a nonempty {field} in {config_file}.')
        section = Path(sys.argv[0]).stem.removeprefix('generate-').removesuffix('-docs')
        section = 'product-deployments' if section == 'products' else section
        project_paths.validate_render_paths([domain_dir], [section])
    except (OSError, ValueError) as error:
        parser.error(str(error))
    site_config = {"domains": [domain]}
    return domain, site_config
