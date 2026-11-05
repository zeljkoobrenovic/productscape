"""Verify the deployment overview prompt, links, label caps, and file handling without live image calls."""
import base64
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import generate_customer_icons_gemini_nanobanana_api as icons
import generate_deployment_overview_image_gemini_nanobanana_api as deployments

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


def brick(brick_id, name, *product_ids):
    return {'brickId': brick_id, 'brickName': name, 'usedInProducts': [{'productId': pid} for pid in product_ids]}


class DeploymentOverviewImage(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='deployment overview ')
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        previous_project = deployments.project_paths.PROJECT_ROOT
        self.addCleanup(deployments.project_paths.configure, previous_project)
        self.domain = self.project / '_config/product-domains/sample/alpha'
        self.write('start/config.json', {'id': 'alpha', 'name': 'Tool Lending', 'description': 'Neighbours borrow tools.'})
        self.write('product-deployments/products.json', {'portfolio': {'products': [
            {'id': 'app', 'name': 'Lending App (beta)', 'type': 'Mobile app', 'description': 'Borrow tools. Long tail here.'},
            {'id': 'desk', 'name': 'Desk Console'},
            {'id': 'idle', 'name': 'Idle Product'},
        ]}})
        self.write('product-deployments/deployment.json', {'channels': [
            {'groupId': 'cloud', 'groupName': 'Public Cloud', 'description': 'Shared runtime. More detail.', 'channels': [
                {'subChannelId': 'api', 'subChannelName': 'API Runtime (k8s)', 'deployedBricks': [
                    brick('cat', 'Catalogue, Search and Availability Signals for Members', 'app', 'desk'),
                    brick('loan', 'Loans', 'app'),
                    brick('pay', 'Payments', 'app'),
                ]},
                {'subChannelId': 'web', 'subChannelName': 'Web Front End', 'deployedBricks': [brick('cat', 'Catalogue', 'app')]},
            ]},
            {'groupId': 'stores', 'groupName': 'App Stores', 'channels': [
                {'subChannelId': 'ios', 'subChannelName': 'iOS', 'deployedBricks': [brick('shell', 'Mobile Shell', 'app')]}]},
            {'groupId': 'empty', 'groupName': 'Empty Group', 'channels': []},
        ]})
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def write(self, relative, payload):
        path = self.domain / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding='utf-8')

    def run_script(self, *extra, api_key='key'):
        args = deployments.parse_args(['--project', str(self.project), '--domain', 'alpha', '--max-width', '0', *extra])
        return deployments.run_generation(args, api_key)

    def test_model_summarizes_products_lanes_and_shared_bricks(self):
        model = deployments.collect_model(self.domain)
        self.assertEqual(model['products'], ['Lending App', 'Desk Console', 'Idle Product'])  # Authored order.
        self.assertEqual([g['name'] for g in model['groups']], ['Public Cloud', 'App Stores'])  # Empty group dropped.
        self.assertEqual(model['groups'][0]['channels'], ['API Runtime', 'Web Front End'])
        self.assertEqual(model['uses'], [{'product': 'Lending App', 'lane': 'Public Cloud'},
                                         {'product': 'Lending App', 'lane': 'App Stores'},
                                         {'product': 'Desk Console', 'lane': 'Public Cloud'}])
        # Both deployed products use the catalogue, so it is shared by every product.
        self.assertEqual((model['shared'], model['shared_by_all']), (['Catalogue, Search'], True))
        self.assertEqual(model['unmapped'], ['Idle Product'])
        self.assertEqual((model['brick_total'], model['shared_total']), (4, 1))

    def test_prompt_draws_structure_without_product_specific_links(self):
        model = deployments.collect_model(self.domain)
        prompt = deployments.build_prompt(model)
        self.assertIn('Bricks used by every product (one continuous row under the products):\n  - "Catalogue, Search"', prompt)
        self.assertIn('Lane "Public Cloud" with channel tiles: "API Runtime", "Web Front End"', prompt)
        self.assertIn('Draw NO individual lines, arrows, or brackets between a specific product', prompt)
        self.assertNotIn('->', prompt)
        self.assertIn('dashed outline): "Idle Product"', prompt)
        self.assertIn('Lending App (beta) (Mobile app): Borrow tools', prompt)
        self.assertNotIn('Long tail', prompt)
        # The alt text still says which product runs where, since the picture does not.
        self.assertIn('Lending App runs on Public Cloud, App Stores', deployments.deployment_alt(model))

    def test_without_a_brick_common_to_all_the_most_shared_are_shown(self):
        self.write('product-deployments/products.json', {'portfolio': {'products': [
            {'id': pid, 'name': pid.title()} for pid in ('one', 'two', 'three')]}})
        self.write('product-deployments/deployment.json', {'channels': [
            {'groupId': 'web', 'groupName': 'Web', 'channels': [{'subChannelId': 'site', 'deployedBricks': [
                brick('pair', 'Pair', 'one', 'two'), brick('solo', 'Solo', 'three'),
                brick('trio', 'Trio', 'two', 'three')]}]}]})
        model = deployments.collect_model(self.domain)
        self.assertEqual((model['shared'], model['shared_by_all']), (['Pair', 'Trio'], False))
        self.assertIn('Most shared bricks (one continuous row', deployments.build_prompt(model))

    def test_compact_label_keeps_head_phrase(self):
        self.assertEqual(deployments.compact_label('B2B Customer Accounts and Self-Service Portal'), 'B2B Customer Accounts')
        self.assertEqual(deployments.compact_label('Merchant Back Office (Wagtail/Oscar dashboard)'), 'Merchant Back Office')
        # One-word heads are rejected; the next separator or a word cut keeps the meaning.
        self.assertEqual(deployments.compact_label('Pricing, Promotions and Purchase Price Formulas', 44), 'Pricing, Promotions')
        self.assertEqual(deployments.compact_label('Platform and Integration Services', 36), 'Platform and Integration Services')
        self.assertEqual(deployments.compact_label('Vendit Hardware, Installation and Support', 40), 'Vendit Hardware')
        self.assertFalse(deployments.compact_label('Very Long Words Repeated Again And Again Forever').endswith('And'))

    def test_dry_run_writes_nothing_and_needs_no_key(self):
        self.assertEqual(self.run_script('--dry-run', api_key=''), 0)
        self.assertFalse((self.domain / 'product-deployments/media').exists())
        self.assertIn('Would generate 1', self.output.getvalue())

    def test_missing_key_is_reported_before_any_call(self):
        with self.assertRaisesRegex(ValueError, 'GEMINI_API_KEY'):
            self.run_script(api_key='')

    def test_domain_without_links_is_skipped(self):
        self.write('product-deployments/deployment.json', {'channels': []})
        self.assertEqual(self.run_script(api_key=''), 0)
        self.assertIn('Skip (no products deployed', self.output.getvalue())

    def test_generation_saves_image_prompt_and_alt_then_reuses(self):
        with patch.object(deployments, 'call_gemini_nanobanana_api', return_value=icons.GeneratedImage(PNG, 'png')) as call:
            self.assertEqual(self.run_script(), 0)
            self.assertEqual(self.run_script(), 0)
        self.assertEqual(call.call_count, 1)
        media = self.domain / 'product-deployments/media'
        self.assertEqual((media / 'deployment-overview.png').read_bytes(), PNG)
        self.assertIn('Public Cloud', (media / 'deployment-overview.prompt.txt').read_text(encoding='utf-8'))
        self.assertIn('Lending App runs on Public Cloud, App Stores',
                      (media / 'deployment-overview.alt.txt').read_text(encoding='utf-8'))

    def test_overwrite_replaces_other_formats(self):
        media = self.domain / 'product-deployments/media'
        media.mkdir(parents=True)
        (media / 'deployment-overview.jpg').write_bytes(b'old')
        with patch.object(deployments, 'call_gemini_nanobanana_api', return_value=icons.GeneratedImage(PNG, 'png')):
            self.assertEqual(self.run_script('--overwrite'), 0)
        self.assertEqual(sorted(p.name for p in media.glob('deployment-overview.*')),
                         ['deployment-overview.alt.txt', 'deployment-overview.png', 'deployment-overview.prompt.txt'])


if __name__ == '__main__':
    unittest.main()
