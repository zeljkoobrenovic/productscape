"""Locate sources in _config/product-domains/<group>/<domain-id>/.

Group names come from the filesystem. Domain IDs stay globally unique so moving
a domain between groups does not change CLI arguments. Published pages live in
docs/<group>/<domain-id>/ and follow the current source group.
The root-level start/ directory contains shared navigation, not a domain group.
"""

import argparse
from pathlib import Path


from project_paths import TOOLKIT_ROOT as REPO_ROOT, DOMAINS_ROOT


def discover_domain_dirs(domains_root=DOMAINS_ROOT):
    """Return domain directories, including domains still being authored."""
    domains = {}
    if not Path(domains_root).exists():
        return []
    for group in sorted(Path(domains_root).iterdir()):
        if not group.is_dir() or group.name.startswith(('.', '_')):
            continue
        if any((group / marker).exists() for marker in (
            'start/config.json', '_domain', 'customers/customers.json',
            'product-bricks/product-bricks.json', 'product-deployments/products.json',
        )):
            raise ValueError(
                f'Domain {group.name!r} is directly under {domains_root}; '
                'move it into a group: <group>/<domain-id>/.'
            )
        if group.name == 'start':
            continue
        for domain in sorted(group.iterdir()):
            if not domain.is_dir() or domain.name.startswith(('.', '_')):
                continue
            if domain.name in domains:
                raise ValueError(
                    f'Duplicate domain ID {domain.name!r}: {domains[domain.name]} and {domain}. '
                    'Domain IDs must be unique across groups.'
                )
            domains[domain.name] = domain
    return [domains[name] for name in sorted(domains)]


def resolve_domain_dir(domain_id, domains_root=DOMAINS_ROOT):
    """Resolve a bare domain ID independently of its current group."""
    for domain in discover_domain_dirs(domains_root):
        if domain.name == domain_id:
            return domain
    raise ValueError(
        f'Unknown domain {domain_id!r}; expected {domains_root}/<group>/{domain_id}/.'
    )


def domain_source_path(domain_id, *parts, domains_root=DOMAINS_ROOT):
    """Return a source path as a string for the existing doc generators."""
    return str(resolve_domain_dir(domain_id, domains_root).joinpath(*parts))


def domain_docs_path(domain_id, *parts, domains_root=DOMAINS_ROOT):
    """Return a published path relative to docs/, using the current source group."""
    domain = resolve_domain_dir(domain_id, domains_root)
    return Path(domain.parent.name, domain.name, *parts).as_posix()


def list_domain_files(relative_path, domain_filter=None, domains_root=DOMAINS_ROOT):
    """Find an artifact across groups, optionally scoped to a single domain ID."""
    domains = (
        [resolve_domain_dir(domain_filter, domains_root)]
        if domain_filter else discover_domain_dirs(domains_root)
    )
    return [domain / relative_path for domain in domains if (domain / relative_path).is_file()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list', help='List registered domain IDs across all groups.')
    resolve = commands.add_parser('resolve', help='Print the source directory for a domain ID.')
    resolve.add_argument('domain_id')
    args = parser.parse_args()
    try:
        if args.command == 'list':
            for config in list_domain_files('start/config.json'):
                print(config.parent.parent.name)
        else:
            print(resolve_domain_dir(args.domain_id))
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
