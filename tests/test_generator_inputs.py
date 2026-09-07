"""Build pages from explicit paths in unrelated directories, without example data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

from test_cli import CLI, TOOLKIT, Links, snapshot


SECTIONS = ('start', 'customers', 'products', 'product-bricks', 'teams', 'competition', 'residuality')
GENERATORS = TOOLKIT / '_wiring/product-domains'


class GeneratorInputs(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='productscape generator inputs ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.project = self.root / 'data project'
        self.output = self.root / 'published site'
        self.env = {key: value for key, value in os.environ.items() if not key.startswith('PRODUCTSCAPES_')}
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'
        self.command(sys.executable, CLI, 'new', 'example', '--group', 'sample', '--project', self.project)
        self.domain = self.project / '_config/product-domains/sample/example'

    def command(self, *arguments, ok=True, env=None):
        result = subprocess.run([str(argument) for argument in arguments], cwd=self.root,
                                env=env or self.env, capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def custom_inputs(self):
        templates = self.root / 'custom templates'
        shared = self.root / 'shared models'
        navigation = self.root / 'domain navigation.json'
        shutil.copytree(TOOLKIT / '_templates', templates)
        shutil.copytree(TOOLKIT / '_config/_shared', shared)
        for section in (*SECTIONS, 'catalog', 'evidence-explorer'):
            folder = 'product-deployments' if section == 'products' else section
            path = templates / folder / 'index.html'
            path.write_text(path.read_text() + f'\n<!-- custom {folder} template -->\n')
        apps = json.loads((TOOLKIT / '_config/product-domains/start/apps.json').read_text())
        apps['apps'][0]['apps'][0]['apps'][0]['name'] = 'Explicit navigation label'
        navigation.write_text(json.dumps(apps))
        team_file = shared / 'team-model.json'
        teams = json.loads(team_file.read_text())
        teams['teamTypes'][0]['name'] = 'Explicit shared team type'
        team_file.write_text(json.dumps(teams))
        return {
            '--output-dir': self.output, '--templates-dir': templates,
            '--navigation-file': navigation, '--shared-config-dir': shared,
        }

    def test_every_generator_resolves_relative_inputs_before_changing_directory(self):
        inputs = self.custom_inputs()
        flags = [value for flag, path in inputs.items() for value in (flag, os.path.relpath(path, self.root))]
        before = snapshot(self.project)
        stale_env = {
            **self.env, 'PRODUCTSCAPES_PROJECT': str(self.root / 'wrong project'),
            'PRODUCTSCAPES_OUTPUT': str(self.root / 'wrong output'),
            'PRODUCTSCAPES_TEMPLATES': str(self.root / 'wrong templates'),
            'PRODUCTSCAPES_NAVIGATION': str(self.root / 'wrong navigation.json'),
            'PRODUCTSCAPES_SHARED_CONFIG': str(self.root / 'wrong models'),
        }
        for section in SECTIONS:
            with self.subTest(section=section):
                self.command(sys.executable, GENERATORS / f'generate-{section}-docs.py',
                             '--domain-dir', os.path.relpath(self.domain, self.root), *flags, env=stale_env)
                folder = 'product-deployments' if section == 'products' else section
                page = self.output / 'sample/example' / folder / 'index.html'
                self.assertIn(f'custom {folder} template', page.read_text())
        self.assertIn('Explicit navigation label', (self.output / 'sample/example/start/index.html').read_text())
        self.assertIn('Explicit shared team type', (self.output / 'sample/example/teams/index.html').read_text())
        self.assertEqual(snapshot(self.project), before)
        self.assertFalse((self.root / 'wrong output').exists())

    def test_runner_uses_absolute_inputs_for_domain_and_shared_site_pages(self):
        inputs = self.custom_inputs()
        package = self.project / '_config/start-packages/example/apps.json'
        package.parent.mkdir(parents=True)
        package.write_text(json.dumps({
            'config': {'name': 'Example package', 'description': 'Example domain catalog', 'showGlobalNav': False},
            'apps': [],
        }))
        before = snapshot(self.project)
        flags = [value for flag, path in inputs.items() for value in (flag, path)]
        self.command('sh', GENERATORS / 'run.sh', self.domain, *flags)
        self.assertEqual(snapshot(self.project), before)
        for section in ('catalog', 'evidence-explorer'):
            page = self.output / ('index.html' if section == 'catalog' else 'evidence-explorer/index.html')
            self.assertIn(f'custom {section} template', page.read_text())
        package_page = self.output / 'start-packages/example/index.html'
        self.assertIn('custom start template', package_page.read_text())
        self.assertTrue((package_page.parent / 'icons/logo.png').is_file())
        # Package pages hide the domain navigation at runtime. Check domain and
        # shared-page links here, and package output/assets separately above.
        pages = [self.output / 'index.html', self.output / 'evidence-explorer/index.html',
                 *(self.output / 'sample/example').rglob('*.html')]
        for page in pages:
            parser = Links()
            parser.feed(page.read_text())
            for url in parser.urls:
                parsed = urlsplit(url)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                self.assertTrue((page.parent / unquote(parsed.path)).exists(), f'{page}: {url}')

    def test_folder_metadata_and_legacy_metadata_overrides_are_supported(self):
        script = GENERATORS / 'generate-start-docs.py'
        page = self.output / 'sample/example/start/index.html'
        self.command(sys.executable, script, self.domain, '--output-dir', self.output,
                     '--name', 'Explicit name', '--description', 'Explicit description')
        self.assertIn('Explicit name', page.read_text())
        self.assertIn('Explicit description', page.read_text())
        self.command(sys.executable, script, 'example', 'Legacy name', 'Legacy description',
                     '--project', self.project, '--output-dir', self.output)
        self.assertIn('Legacy name', page.read_text())
        self.assertIn('Legacy description', page.read_text())

    def test_help_and_invalid_paths_preserve_sources_and_previous_output(self):
        self.output.mkdir()
        (self.output / 'previous.html').write_text('Previous build')
        output_link = self.root / 'output symlink'
        output_link.symlink_to(self.output, target_is_directory=True)
        before = snapshot(self.project)
        output_before = snapshot(self.output)
        for section in SECTIONS:
            result = self.command(sys.executable, GENERATORS / f'generate-{section}-docs.py', '--help')
            self.assertIn('--domain-dir', result.stdout)
            self.assertIn('--templates-dir', result.stdout)
        self.assertIn('--all', self.command('sh', GENERATORS / 'run.sh', '--help').stdout)
        for flags, message in (
            (['--domain-dir', self.domain / 'missing'], 'Domain folder does not exist'),
            (['--domain-dir', self.domain, '--project', self.root], '--project does not contain'),
            (['--domain-dir', self.domain, '--templates-dir', self.root / 'missing'], 'Input directory does not exist'),
            (['--domain-dir', self.domain, '--navigation-file', self.root / 'missing.json'], 'Navigation file does not exist'),
            (['--domain-dir', self.domain, '--output-dir', self.domain], 'overlaps an input'),
            (['--domain-dir', self.domain, '--output-dir', output_link], 'must not be a symlink'),
        ):
            with self.subTest(flags=flags):
                result = self.command(sys.executable, GENERATORS / 'generate-start-docs.py',
                                      '--output-dir', self.output, *flags, ok=False)
                self.assertIn(message, result.stderr)
        self.assertEqual(snapshot(self.project), before)
        self.assertEqual(snapshot(self.output), output_before)


if __name__ == '__main__':
    unittest.main()
