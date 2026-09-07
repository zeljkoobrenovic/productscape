import json
import os
import shutil

from domain_cli import load_domain_args
from generator_common import domain_docs_path, domain_source_path, copy_icons, enter_docs_root, today_string

from generator_common import template_path

domain, _ = load_domain_args()
enter_docs_root()

date_string = today_string()

from generator_common import navigation_path
apps = json.load(open(navigation_path()))

templates_root = template_path('start')

tabs_style = open(templates_root + '../_imports/tabs/style.html').read()
tokens_style = open(templates_root + '../_imports/tokens/style.html').read()
tabs_script = open(templates_root + '../_imports/tabs/script.html').read()


def create_docs(domain, docs_folder):
    source_icons = domain_source_path(domain['id'], 'start/icons')
    if os.path.exists(docs_folder): shutil.rmtree(docs_folder)
    os.makedirs(os.path.join(docs_folder, 'icons'), exist_ok=True)

    copy_icons(templates_root + 'icons', docs_folder)
    copy_icons(source_icons, docs_folder)

    with open(os.path.join(docs_folder, 'index.html'), 'w') as html_file:
        template = open(templates_root + 'index.html').read()
        print(domain['description'])
        html_file.write(template
                        .replace('${tabs_style}', tabs_style)
                        .replace('${tokens_style}', tokens_style)
                        .replace('${tabs_script}', tabs_script)
                        .replace('${date}', date_string)
                        .replace('${apps}', json.dumps(apps))
                        .replace('${domain_nav_links}', '<a href="../residuality/index.html">Stress Test</a>')
                        .replace('${domain_name}', domain['name'])
                        .replace('${domain_description}', domain['description']))


docs_folder = domain_docs_path(domain['id'], 'start') + '/'
create_docs(domain, docs_folder)
