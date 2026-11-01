"""Verify the domain overview prompt, label caps, and file handling without live image calls."""
import base64
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import generate_customer_icons_gemini_nanobanana_api as icons
import generate_domain_overview_image_gemini_nanobanana_api as overview

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class DomainOverviewImage(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='domain overview ')
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        previous_project = overview.project_paths.PROJECT_ROOT
        self.addCleanup(overview.project_paths.configure, previous_project)
        self.domain = self.project / '_config/product-domains/sample/alpha'
        self.write('start/config.json', {'id': 'alpha', 'name': 'Tool Lending', 'description': 'Neighbours borrow tools.'})
        self.write('customers/customers.json', [
            {'group': 'Borrowers', 'customers': [{'name': 'Weekend Fixer'}, {'name': 'Student'}]},
            {'group': 'Volunteers', 'customers': [{'name': 'Desk Volunteer'}]},
        ])
        self.write('product-deployments/products.json', {'portfolio': {'products': [
            {'id': f'p{i}', 'name': f'Product {i} (beta)', 'description': 'Lends tools. Has a long tail of detail.'}
            for i in range(6)]}})
        self.write('product-deployments/deployment.json', {'channels': [
            {'groupId': 'web', 'groupName': 'Web', 'channels': [{'subChannelId': 'site', 'subChannelName': 'Site'}]}]})
        self.write('product-bricks/product-bricks.json', {'rootGroups': [
            {'name': 'Catalogue', 'bricks': [{'id': 'b1', 'externalSystemsThisBrickDependsOn': [
                {'system': 'Stripe', 'type': 'payment'}, {'system': 'Browsers', 'type': 'channel-consumer'}]}]},
            {'name': 'Loans', 'subGroups': [{'name': 'Desk', 'bricks': [
                {'id': 'b2', 'externalSystemsDependingOnThisBrick': [{'system': 'Mailer', 'type': 'crm'}]},
                {'id': 'b3'}]}]},
        ]})
        self.write('business/competition.json', {'players': [
            {'name': 'Small Shop', 'category': 'challenger'}, {'name': 'Big Rental (EU)', 'category': 'global_leader'}]})
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def write(self, relative, payload):
        path = self.domain / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding='utf-8')

    def run_script(self, *extra, api_key='key'):
        # Shrinking is covered separately; keep provider bytes intact here.
        args = overview.parse_args(['--project', str(self.project), '--domain', 'alpha', '--max-width', '0', *extra])
        return overview.run_generation(args, api_key)

    def test_model_caps_labels_and_reads_external_world(self):
        model = overview.collect_model(self.domain)
        self.assertEqual(model['customers'], ['Borrowers', 'Volunteers'])
        self.assertEqual(len(model['products']), overview.LIMITS['products'])
        self.assertEqual(model['products'][0], 'Product 0')
        self.assertEqual(model['brick_groups'], ['Loans', 'Catalogue'])  # Largest group first.
        self.assertEqual(model['brick_total'], 3)
        self.assertEqual(model['external'], ['Payment providers', 'CRM'])  # Customer devices skipped.
        self.assertEqual(model['competitors'], ['Big Rental', 'Small Shop'])  # Leaders first.
        prompt = overview.build_prompt(model)
        self.assertIn('Product 0 (beta): Lends tools;', prompt)  # First sentence only.
        self.assertNotIn('long tail', prompt)
        self.assertIn('  - Payment providers', prompt)
        self.assertNotIn('Browsers', prompt)

    def test_dry_run_writes_nothing_and_needs_no_key(self):
        self.assertEqual(self.run_script('--dry-run', api_key=''), 0)
        self.assertFalse((self.domain / 'start/media').exists())
        self.assertIn('Would generate 1', self.output.getvalue())

    def test_missing_key_is_reported_before_any_call(self):
        with self.assertRaisesRegex(ValueError, 'GEMINI_API_KEY'):
            self.run_script(api_key='')

    def test_generation_saves_image_prompt_and_alt_then_reuses(self):
        image = icons.GeneratedImage(PNG, 'png')
        with patch.object(overview, 'call_gemini_nanobanana_api', return_value=image) as call:
            self.assertEqual(self.run_script(), 0)
            self.assertEqual(self.run_script(), 0)
        self.assertEqual(call.call_count, 1)
        media = self.domain / 'start/media'
        self.assertEqual((media / 'domain-overview.png').read_bytes(), PNG)
        self.assertIn('Tool Lending', (media / 'domain-overview.prompt.txt').read_text(encoding='utf-8'))
        self.assertIn('Overview of Tool Lending', (media / 'domain-overview.alt.txt').read_text(encoding='utf-8'))

    def test_overwrite_replaces_other_formats(self):
        media = self.domain / 'start/media'
        media.mkdir(parents=True)
        (media / 'domain-overview.jpg').write_bytes(b'old')
        with patch.object(overview, 'call_gemini_nanobanana_api', return_value=icons.GeneratedImage(PNG, 'png')):
            self.assertEqual(self.run_script('--overwrite'), 0)
        self.assertEqual(sorted(p.name for p in media.glob('domain-overview.*')),
                         ['domain-overview.alt.txt', 'domain-overview.png', 'domain-overview.prompt.txt'])

    @unittest.skipUnless(overview.shutil.which('sips'), 'sips is macOS-only')
    def test_shrink_converts_to_jpeg_and_keeps_narrow_images_unscaled(self):
        shrunk = overview.shrink_image(PNG, 1600)
        self.assertIsNotNone(shrunk)
        data, fmt = shrunk
        self.assertEqual(fmt, 'jpg')
        self.assertTrue(data.startswith(b'\xff\xd8'))

    def test_shrink_is_skipped_without_sips_or_width(self):
        self.assertIsNone(overview.shrink_image(PNG, 0))
        with patch.object(overview.shutil, 'which', return_value=None):
            self.assertIsNone(overview.shrink_image(PNG, 1600))


if __name__ == '__main__':
    unittest.main()
