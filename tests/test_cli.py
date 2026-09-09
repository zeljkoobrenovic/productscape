"""Exercise public commands with isolated data projects and no example checkout."""
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

TOOLKIT = Path(__file__).resolve().parents[1]
CLI = TOOLKIT / 'productscapes.py'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(value for key, value in attrs if key in ('href', 'src') and value)


def snapshot(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


class ToolkitCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='productscapes test ')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'data project'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('PRODUCTSCAPES_')}
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'

    def command(self, *args, ok=True, launcher=False):
        entry = self.project / 'productscapes.py' if launcher else CLI
        extra = [] if launcher else ['--project', str(self.project)]
        result = subprocess.run([sys.executable, str(entry), *args, *extra], env=self.env,
                                cwd=self.temp.name, capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def create(self, domain='test-domain', group='sample'):
        self.command('new', domain, '--group', group, '--name', 'A "quoted" domain')
        return self.project / '_config/product-domains' / group / domain

    def test_fresh_project_validates_builds_and_has_working_static_links(self):
        domain = self.create()
        self.command('validate', 'test-domain', '--strict-ids', launcher=True)
        before = snapshot(self.project / '_config')
        self.command('build', 'test-domain', launcher=True)
        self.assertEqual(snapshot(self.project / '_config'), before)
        self.assertEqual(json.loads((domain / 'start/config.json').read_text())['name'], 'A "quoted" domain')
        self.assertEqual(json.loads((domain / 'customers/customers.json').read_text()), [])
        for section in ('start', 'customers', 'product-deployments', 'product-bricks', 'teams', 'competition', 'residuality'):
            self.assertTrue((self.project / 'docs/sample/test-domain' / section / 'index.html').is_file(), section)
        self.assertTrue((self.project / 'docs/evidence-explorer/index.html').is_file())
        for page in (self.project / 'docs').rglob('*.html'):
            parser = Links()
            parser.feed(page.read_text())
            for url in parser.urls:
                parsed = urlsplit(url)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                self.assertTrue((page.parent / unquote(parsed.path)).exists(), f'{page}: {url}')

    def test_domain_ids_are_unique_across_groups_and_paths_cannot_escape(self):
        self.create()
        before = snapshot(self.project)
        self.assertIn('already exists', self.command('new', 'test-domain', '--group', 'another', ok=False).stderr)
        for domain, group in (('../escape', 'sample'), ('bad-id', '../escape'), ('UPPER', 'sample'), ('other', 'start')):
            self.command('new', domain, '--group', group, ok=False)
        self.assertEqual(snapshot(self.project), before)

    def test_team_headcounts_preserve_unknown_zero_and_nested_totals(self):
        domain = self.create()

        def team(team_id, **fields):
            return {'id': team_id, 'name': team_id, 'type': 'enabling', **fields}

        payload = {'groups': [
            {'name': 'Unknown', 'teams': [team('missing'), team('null', teamHeadcount={'headcount': None})]},
            {'name': 'Zero', 'groupDirectHeadcount': {'headcount': 0},
             'teams': [team('zero', teamHeadcount={'headcount': 0})]},
            {'name': 'Known', 'groupDirectHeadcount': {'headcount': 1},
             'teams': [team('known', teamHeadcount={'headcount': 3})],
             'groups': [{'name': 'Known child', 'groupDirectHeadcount': {'headcount': 2},
                         'teams': [team('child', teamHeadcount={'headcount': 4})]}]},
            {'name': 'Mixed', 'groupDirectHeadcount': {'headcount': 0},
             'teams': [team('sized', teamHeadcount={'headcount': 2})],
             'groups': [{'name': 'Unknown child', 'groupDirectHeadcount': {'headcount': 0},
                         'teams': [team('unsized')]}]},
        ]}
        (domain / 'teams/teams.json').write_text(json.dumps(payload))
        before = snapshot(self.project / '_config')
        self.command('build', 'test-domain', '--sections', 'teams')
        self.assertEqual(snapshot(self.project / '_config'), before)
        page = (self.project / 'docs/sample/test-domain/teams/index.html').read_text()
        data, _ = json.JSONDecoder().raw_decode(page.split('const teamsData = ', 1)[1])
        unknown, zero, known, mixed = data['groups']
        self.assertIsNone(unknown['teamHeadcount'])
        self.assertIsNone(unknown['groupDirectHeadcount']['headcount'])
        self.assertIsNone(unknown['rollupHeadcount'])
        self.assertEqual(zero['rollupHeadcount'], 0)
        self.assertEqual(known['rollupHeadcount'], 10)
        self.assertEqual(mixed['teamHeadcount'], 2)
        self.assertIsNone(mixed['rollupHeadcount'])

    def test_bad_inputs_preserve_previous_output(self):
        domain = self.create()
        target = self.project / 'docs/sample/test-domain/start/index.html'
        target.parent.mkdir(parents=True)
        target.write_text('previous build')
        (domain / 'customers/customers.json').write_text('{broken')
        self.command('build', 'test-domain', ok=False)
        self.assertEqual(target.read_text(), 'previous build')
        (domain / 'customers/customers.json').unlink()
        self.assertIn('missing required sources', self.command('build', 'test-domain', ok=False).stderr)
        self.assertEqual(target.read_text(), 'previous build')

    def test_unknown_and_unregistered_domains_fail_clearly(self):
        self.project.mkdir()
        self.assertIn('No registered domains', self.command('build', '--all', ok=False).stderr)
        self.assertIn('Unknown domain', self.command('validate', 'absent', ok=False).stderr)

    def test_images_dry_run_is_read_only_without_api_keys(self):
        self.create()
        self.env.pop('GEMINI_API_KEY', None)
        self.env.pop('OPENAI_API_KEY', None)
        before = snapshot(self.project)
        self.command('images', 'test-domain', '--dry-run', '--lightweight', '--skip-existing', launcher=True)
        self.assertEqual(snapshot(self.project), before)

    def test_two_projects_do_not_share_domain_sources(self):
        self.create()
        first = self.project
        before = snapshot(first)
        self.project = Path(self.temp.name) / 'second project'
        self.create(group='another')
        self.assertEqual(self.command('list', launcher=True).stdout.strip(), 'another/test-domain')
        self.assertEqual(snapshot(first), before)

    def test_launcher_reports_missing_toolkit_and_wrong_pin(self):
        self.create()
        config_path = self.project / 'productscapes.json'
        config = json.loads(config_path.read_text())
        config['revision'] = '0' * 40
        config_path.write_text(json.dumps(config))
        self.assertIn('requires productscapes commit', self.command('list', launcher=True, ok=False).stderr)
        config['toolkit'] = '../missing toolkit'
        config_path.write_text(json.dumps(config))
        self.assertIn('toolkit not found', self.command('list', launcher=True, ok=False).stderr)

    def test_skills_install_with_shared_references_without_generator_copies(self):
        self.create()
        self.command('skills', '--target', '.agents/skills', launcher=True)
        installed = self.project / '.agents/skills'
        self.assertTrue((installed / '_references/domain-model.md').is_file())
        self.assertTrue((installed / 'new-product-domain/SKILL.md').is_file())
        self.assertFalse((installed / 'scripts').exists())
        self.command('skills', launcher=True, ok=False)


if __name__ == '__main__':
    unittest.main()
