"""Exercise a newcomer tutorial through authoring, validation, and static rendering."""
from copy import deepcopy
import base64
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_cli import CLI, TOOLKIT, snapshot

sys.path.insert(0, str(TOOLKIT / '_wiring'))
from tutorial_model import validate_tutorial

EXAMPLE = TOOLKIT / 'skills/create-domain-tutorial/assets/example-tutorial.json'
GENERATOR = TOOLKIT / '_wiring/product-domains/generate-tutorial-docs.py'


class ReadingPage(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.ids = []
        self.links = []
        self.tags = []
        self.disclosures = []
        self.images = []
        self.link_attributes = []
        self.text = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append(tag)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs['href'])
            self.link_attributes.append(attrs)
        if tag == 'img':
            self.images.append(attrs)
        if tag == 'details':
            self.disclosures.append(attrs)

    def handle_data(self, data):
        self.text.append(data)


class Tutorial(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='productscape tutorial ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.project = self.root / 'data project'
        self.env = {key: value for key, value in os.environ.items() if not key.startswith('PRODUCTSCAPES_')}
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'
        self.command(CLI, 'new', 'tool-lending', '--group', 'sample', '--project', self.project)
        self.domain = self.project / '_config/product-domains/sample/tool-lending'
        self.source = self.domain / 'tutorial/tutorial.json'
        self.page = self.project / 'docs/sample/tool-lending/tutorial/index.html'
        self.example = json.loads(EXAMPLE.read_text(encoding='utf-8'))

    def command(self, script, *arguments, ok=True):
        result = subprocess.run([sys.executable, str(script), *map(str, arguments)], cwd=self.root,
                                env=self.env, capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def write_example(self):
        self.source.write_text(json.dumps(self.example, ensure_ascii=False), encoding='utf-8')

    def test_worked_example_builds_readable_content_and_navigation_without_source_changes(self):
        self.write_example()
        before = snapshot(self.project / '_config')
        self.command(CLI, 'validate', 'tool-lending', '--strict-ids', '--project', self.project)
        self.command(CLI, 'build', 'tool-lending', '--project', self.project)
        self.assertEqual(snapshot(self.project / '_config'), before)
        page = ReadingPage(self.page.read_text(encoding='utf-8'))
        self.assertEqual(len(page.ids), len(set(page.ids)))
        for link in page.links:
            if link.startswith('#'):
                self.assertIn(link[1:], page.ids)
        self.assertIn('../start/index.html', page.links)
        home = ReadingPage((self.page.parent.parent / 'start/index.html').read_text(encoding='utf-8'))
        self.assertIn('../tutorial/index.html', home.links)
        self.assertEqual(len(page.disclosures), len(self.example['knowledgeChecks']))
        self.assertTrue(all('open' not in attrs for attrs in page.disclosures))
        for value in (self.example['walkthrough']['outcome'], self.example['history'][0]['change'],
                      self.example['challenges'][0]['tradeOff'], self.example['knowledgeChecks'][0]['answer'],
                      self.example['knowledgeChecks'][0]['explanation']):
            self.assertIn(value, page.text)
        self.assertNotIn('script', page.tags)
        self.assertNotIn('link', page.tags)  # No external stylesheet or font needed to read.
        self.assertNotIn('${', self.page.read_text(encoding='utf-8'))

    def test_drafts_and_older_domains_without_tutorials_build_without_invented_content(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    self.source.unlink()
                before = snapshot(self.project / '_config')
                self.command(CLI, 'build', 'tool-lending', '--sections', 'tutorial', '--project', self.project)
                page = ReadingPage(self.page.read_text(encoding='utf-8'))
                self.assertIn('This introduction is not written yet', page.text)
                self.assertNotIn('history', page.ids)
                self.assertFalse(page.disclosures)
                self.assertEqual(snapshot(self.project / '_config'), before)

    def test_ready_contract_rejects_incomplete_mismatched_or_unsafe_inputs(self):
        cases = []
        for key in ('history', 'challenges', 'knowledgeChecks', 'scope'):
            payload = deepcopy(self.example)
            del payload[key]
            cases.append((key, payload))
        for key, value in (('concepts', []), ('participants', {}), ('domainId', 'different-domain'),
                           ('title', '  '), ('updated', '2026-02-30'), ('rawHtml', '<b>text</b>')):
            payload = deepcopy(self.example)
            payload[key] = value
            cases.append((key, payload))
        for url in ('javascript:alert(1)', 'https:///missing-host', 'https://user:secret@example.com/', 'https://example.com:bad/'):
            payload = deepcopy(self.example)
            payload['history'][0]['sourceUrl'] = url
            cases.append(('sourceUrl', payload))
        for label, payload in cases:
            with self.subTest(label=label, payload=payload):
                self.assertTrue(validate_tutorial(payload, 'tool-lending'))
        self.assertEqual(validate_tutorial(self.example, 'tool-lending'), [])

    def test_bad_tutorial_preserves_previous_site_in_cli_and_direct_generator(self):
        self.page.parent.mkdir(parents=True)
        self.page.write_text('Previous tutorial')
        home = self.page.parent.parent / 'start/index.html'
        home.parent.mkdir()
        home.write_text('Previous home')
        self.example['knowledgeChecks'] = []
        self.write_example()
        before = snapshot(self.project / 'docs')
        result = self.command(CLI, 'build', 'tool-lending', '--project', self.project, ok=False)
        self.assertIn('knowledgeChecks', result.stderr)
        self.command(CLI, 'validate', 'tool-lending', '--project', self.project, ok=False)
        self.command(GENERATOR, '--domain-dir', self.domain, ok=False)
        self.assertEqual(snapshot(self.project / 'docs'), before)

    def test_plain_text_is_escaped_and_never_interpreted_as_template_code(self):
        text = '<script>alert("hello")</script> & ${title}'
        self.example['introduction']['whatItIs'] = text
        self.write_example()
        self.command(GENERATOR, '--domain-dir', self.domain)
        page = ReadingPage(self.page.read_text(encoding='utf-8'))
        self.assertIn(text, page.text)
        self.assertNotIn('script', page.tags)

    def test_direct_preview_needs_only_metadata_and_tutorial_and_supports_partial_drafts(self):
        domain = self.root / 'minimal project/_config/product-domains/learning/tool-lending'
        (domain / 'start').mkdir(parents=True)
        (domain / 'start/config.json').write_text(json.dumps({
            'name': 'Tool lending', 'description': 'An introduction to borrowing tools.'}))
        (domain / 'tutorial').mkdir()
        self.example['status'] = 'draft'
        del self.example['history']
        (domain / 'tutorial/tutorial.json').write_text(json.dumps(self.example))
        before = snapshot(domain)
        output = self.root / 'preview'
        self.command(GENERATOR, '--domain-dir', domain, '--output-dir', output)
        self.assertEqual(snapshot(domain), before)
        page = ReadingPage((output / 'learning/tool-lending/tutorial/index.html').read_text(encoding='utf-8'))
        self.assertIn('Draft introduction', page.text)
        self.assertIn(self.example['walkthrough']['outcome'], page.text)
        self.assertNotIn('history', page.ids)
        self.assertNotIn('../start/index.html', page.links)

    def test_installed_skill_keeps_its_worked_example_and_format_reference(self):
        self.command(CLI, 'skills', '--project', self.project)
        installed = self.project / '.agents/skills/create-domain-tutorial'
        self.assertEqual((installed / 'assets/example-tutorial.json').read_bytes(), EXAMPLE.read_bytes())
        self.assertTrue((installed / 'references/tutorial-format.md').is_file())
        self.assertTrue((installed / 'agents/openai.yaml').is_file())

    def test_concept_and_overview_images_copy_in_reading_order_and_open_in_new_tabs(self):
        media = {'id': 'concept-illustration', 'type': 'image', 'src': 'media/reservation.png',
                 'alt': 'A borrower & a drill.', 'title': 'A "reservation"',
                 'caption': '<A booking> is not collection.'}
        self.example['concepts'][0]['media'] = [media]
        participant_map = {**media, 'id': 'participants-overview', 'src': 'media/participants.png',
                           'alt': 'A borrower and library staff exchange a drill.'}
        walkthrough = {**media, 'id': 'walkthrough-overview', 'src': 'media/walkthrough.png',
                       'alt': 'Maya books, borrows, and returns the drill.'}
        self.example['participantsOverview'] = {'media': [participant_map]}
        self.example['walkthrough']['media'] = [walkthrough]
        self.write_example()
        image = self.source.parent / media['src']
        image.parent.mkdir()
        image.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='))
        image.with_suffix('.prompt.txt').write_text('Source prompt only')
        for item in (participant_map, walkthrough):
            (self.source.parent / item['src']).write_bytes(image.read_bytes())
        before = snapshot(self.project / '_config')
        self.env.pop('GEMINI_API_KEY', None)
        self.env.pop('GOOGLE_API_KEY', None)
        self.command(CLI, 'images', 'tool-lending', '--kind', 'tutorial', '--dry-run', '--project', self.project)
        self.command(CLI, 'validate', 'tool-lending', '--project', self.project)
        self.command(CLI, 'build', 'tool-lending', '--sections', 'tutorial', '--project', self.project)
        page = ReadingPage(self.page.read_text())
        expected = (participant_map, media, walkthrough)
        self.assertEqual([image['src'] for image in page.images], [item['src'] for item in expected])
        for rendered, item in zip(page.images, expected):
            self.assertEqual(rendered['alt'], item['alt'])
            link = next(link for link in page.link_attributes if link['href'] == item['src'])
            self.assertEqual(link['target'], '_blank')
            self.assertIn('noopener', link['rel'].split())
            self.assertIn('new tab', link['aria-label'])
            self.assertEqual((self.page.parent / item['src']).read_bytes(), image.read_bytes())
        self.assertIn(media['caption'], page.text)
        self.assertEqual((self.page.parent / media['src']).read_bytes(), image.read_bytes())
        self.assertFalse((self.page.parent / 'media/reservation.prompt.txt').exists())
        self.assertEqual(snapshot(self.project / '_config'), before)

    def test_overviews_require_safe_existing_assets_and_participant_context(self):
        self.page.parent.mkdir(parents=True)
        self.page.write_text('Previous tutorial')
        for owner in ('participantsOverview', 'walkthrough'):
            with self.subTest(owner=owner):
                self.example.setdefault(owner, {})['media'] = [
                    {'type': 'image', 'src': 'media/absent.png', 'alt': 'An overview.'}]
                self.write_example()
                result = self.command(GENERATOR, '--domain-dir', self.domain, ok=False)
                self.assertIn(f'$.{owner}.media[0].src', result.stderr)
                self.assertEqual(self.page.read_text(), 'Previous tutorial')
                self.example[owner]['media'][0]['src'] = 'media/../outside.png'
                self.assertTrue(validate_tutorial(self.example, 'tool-lending'))
                del self.example[owner]['media']
        self.example['participantsOverview'] = {'illustrationPrompt': 'Map the people.'}
        self.example['participants'] = []
        self.assertTrue(any('participantsOverview' in error for error in validate_tutorial(self.example, 'tool-lending')))

    def test_missing_and_escaping_images_preserve_the_previous_page(self):
        self.example['concepts'][0]['media'] = [
            {'type': 'image', 'src': 'media/missing.png', 'alt': 'A drill.'}]
        self.write_example()
        self.page.parent.mkdir(parents=True)
        self.page.write_text('Previous tutorial')
        before = snapshot(self.project / 'docs')
        for mode in ('missing', 'symlink'):
            with self.subTest(mode=mode):
                if mode == 'symlink':
                    outside = self.root / 'outside'
                    outside.mkdir()
                    (outside / 'missing.png').write_bytes(b'outside image')
                    (self.source.parent / 'media').symlink_to(outside, target_is_directory=True)
                self.command(CLI, 'validate', 'tool-lending', '--project', self.project, ok=False)
                self.command(CLI, 'build', 'tool-lending', '--sections', 'tutorial', '--project', self.project, ok=False)
                self.command(GENERATOR, '--domain-dir', self.domain, ok=False)
                self.assertEqual(snapshot(self.project / 'docs'), before)
        for src in ('../outside.png', '/tmp/image.png', 'https://example.com/image.png',
                    'media/../outside.png', 'media/a.svg', 'media/a.png?query', 'media/%2e%2e/a.png'):
            with self.subTest(src=src):
                self.example['concepts'][0]['media'][0]['src'] = src
                self.assertTrue(validate_tutorial(self.example, 'tool-lending'))


if __name__ == '__main__':
    unittest.main()
