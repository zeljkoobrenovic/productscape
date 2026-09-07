import copy
import datetime
import json
import shutil
from pathlib import Path
from urllib.parse import urlparse

from domain_paths import discover_domain_dirs, domain_docs_path

from project_paths import PROJECT_ROOT, DOCS_ROOT, TEMPLATES_ROOT as SITE_TEMPLATES_ROOT

DATE_STRING = datetime.date.today().strftime('%Y-%m-%d')

TEMPLATES_ROOT = SITE_TEMPLATES_ROOT / 'start'
IMPORTS_ROOT = SITE_TEMPLATES_ROOT / '_imports'
PACKAGES_ROOT = PROJECT_ROOT / '_config' / 'start-packages'
DOCS_PACKAGES_ROOT = DOCS_ROOT / 'start-packages'

TABS_STYLE = (IMPORTS_ROOT / 'tabs' / 'style.html').read_text(encoding='utf-8')
TOKENS_STYLE = (IMPORTS_ROOT / 'tokens' / 'style.html').read_text(encoding='utf-8')
TABS_SCRIPT = (IMPORTS_ROOT / 'tabs' / 'script.html').read_text(encoding='utf-8')


def copy_icons(icons_path, docs_folder):
    if not icons_path.exists():
        return

    icons_folder = docs_folder / 'icons'
    icons_folder.mkdir(parents=True, exist_ok=True)

    for src in sorted(icons_path.iterdir()):
        if src.is_file():
            shutil.copy2(src, icons_folder / src.name)


def is_external_url(value):
    parsed = urlparse(value)
    return bool(parsed.scheme or parsed.netloc)


def rebase_start_apps_url(value):
    if not isinstance(value, str) or is_external_url(value):
        return value

    parsed = urlparse(value)
    parts = parsed.path.split('/')
    domains = {domain.name for domain in discover_domain_dirs()}

    # Resolve both historical flat links and current package-relative group links.
    # Looking up the domain ID also repairs links after its source group changes.
    if parts[:2] == ['..', 'product-domains']:
        domain_index = 2
    elif parts[:3] == ['..', '..', 'product-domains']:
        domain_index = 3
    elif parts[:2] == ['..', '..'] and len(parts) > 3 and parts[3] in domains:
        domain_index = 3
    else:
        return value

    if len(parts) <= domain_index:
        return value
    published_path = domain_docs_path(parts[domain_index], *parts[domain_index + 1:])
    return parsed._replace(path='../../' + published_path).geturl()


def rebase_app_links(apps):
    apps = copy.deepcopy(apps)
    for tab in apps.get('apps', []):
        for group in tab.get('apps', []):
            for app in group.get('apps', []):
                for field in ('link', 'icon'):
                    if field in app:
                        app[field] = rebase_start_apps_url(app[field])
    return apps


def package_title(package_name):
    return package_name.replace('-', ' ').replace('_', ' ').title()


def package_config(apps, package_name):
    config = apps.get('config', {})
    name = config.get('name') or config.get('domainName') or config.get('domain_name') or config.get('title')
    description = config.get('description') or config.get('domainDescription') or config.get('domain_description')

    if not name:
        raise ValueError(f'Missing config.name in {PACKAGES_ROOT / package_name / "apps.json"}')
    if not description:
        raise ValueError(f'Missing config.description in {PACKAGES_ROOT / package_name / "apps.json"}')

    return {
        'domain_name': name,
        'domain_description': description,
        'package_title': config.get('packageTitle') or config.get('package_title') or name or package_title(package_name),
    }


def package_sources():
    if not PACKAGES_ROOT.exists():
        raise FileNotFoundError(f'Missing start packages folder: {PACKAGES_ROOT}')

    packages = []
    for package_folder in sorted(PACKAGES_ROOT.iterdir()):
        if not package_folder.is_dir() or package_folder.name.startswith('.'):
            continue
        apps_json = package_folder / 'apps.json'
        if apps_json.exists():
            packages.append(package_folder)

    if not packages:
        raise FileNotFoundError(f'No start package apps.json files found in: {PACKAGES_ROOT}')

    return packages


def render_package(package_folder, template):
    package_name = package_folder.name
    with (package_folder / 'apps.json').open(encoding='utf-8') as apps_file:
        apps = json.load(apps_file)

    rendered_apps = rebase_app_links(apps)
    config = package_config(apps, package_name)

    output_folder = DOCS_PACKAGES_ROOT / package_name
    if output_folder.exists():
        shutil.rmtree(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    copy_icons(TEMPLATES_ROOT / 'icons', output_folder)
    copy_icons(package_folder / 'icons', output_folder)

    with (output_folder / 'index.html').open('w', encoding='utf-8') as html_file:
        html_file.write(
            template
            .replace('${tabs_style}', TABS_STYLE)
            .replace('${tokens_style}', TOKENS_STYLE)
            .replace('${tabs_script}', TABS_SCRIPT)
            .replace('${date}', DATE_STRING)
            .replace('${apps}', json.dumps(rendered_apps))
            .replace('${domain_nav_links}', '')
            .replace('${domain_name}', config['domain_name'])
            .replace('${domain_description}', config['domain_description'])
        )

    return config['package_title'], output_folder


def main():
    template = (TEMPLATES_ROOT / 'index.html').read_text(encoding='utf-8')
    rendered_packages = []

    for package_folder in package_sources():
        rendered_packages.append(render_package(package_folder, template))

    for package_title_value, output_folder in rendered_packages:
        print(f'Generated {package_title_value}: {output_folder}')


if __name__ == '__main__':
    main()
