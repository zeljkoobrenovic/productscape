"""Commercial-model integrity, safe rendering, and non-destructive CLI behavior."""
from copy import deepcopy
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
from value_growth_model import market_totals, validate_value_growth

GENERATOR = TOOLKIT / '_wiring/product-domains/generate-value-growth-docs.py'


def example():
    evidence = {'kind': 'illustrative', 'note': 'Fictional service for contract tests.', 'sourceIds': []}
    return {
        'schemaVersion': '1.0', 'domainId': 'example', 'status': 'ready', 'title': 'Value & Growth',
        'updated': '2026-11-16', 'summary': 'Commercial model for a fictional service.', 'scope': 'An explicit example, not market research.',
        'framework': {'summary': 'Compare the same customer job.', 'strategies': [
            {'id': 'differentiated', 'name': 'Differentiated', 'definition': 'Better outcomes at a premium.'}], 'evidence': evidence},
        'segments': [{
            'id': 'teams', 'name': 'Small teams', 'summary': 'A team service.', 'customerRefs': [], 'productIds': [], 'competitorIds': [],
            'outcome': 'Complete work reliably.', 'valueUnit': 'Completed team workflows', 'pricingUnit': 'Active team',
            'pricingModel': 'Annual subscription', 'valueProof': 'Observe repeated successful workflows.',
            'selling': {'motion': 'bottom-up', 'users': 'Team members', 'champions': 'Team lead', 'buyers': 'Team lead', 'payers': 'Company', 'channels': ['Self-service'], 'rationale': 'A team can establish value.'},
            'positioning': {'strategy': 'differentiated', 'alternative': 'Manual coordination', 'rationale': 'More reliable outcomes.', 'conditions': ['Customers pay for the improvement.']},
            'activation': {'entry': 'Trial', 'firstValue': 'First successful workflow', 'repeatValue': 'Weekly completion', 'expansion': 'More teams', 'frictions': ['Setup']},
            'evidence': evidence}],
        'market': {'summary': 'Hypothetical account-based market.', 'boundary': 'A bounded annual revenue pool.', 'context': [], 'exclusions': ['Other service categories'], 'scenarios': [{
            'id': 'base', 'name': 'Illustrative base', 'geography': 'Fictional region', 'baseYear': 2026, 'horizonYears': 3, 'currency': 'EUR',
            'unitLabel': 'Eligible accounts', 'revenueLabel': 'Annual revenue per account', 'units': 10000, 'revenuePerUnit': 120,
            'serviceableShare': 0.4, 'obtainableShare': 0.1, 'assumptions': ['All inputs are illustrative.'], 'limitations': ['Not a forecast.'], 'evidence': evidence}]},
        'economics': [{'id': 'contribution', 'name': 'Contribution', 'formula': 'Revenue minus direct costs', 'whyItMatters': 'Assess cost to serve.', 'measurementCautions': 'Keep the cost boundary consistent.', 'availability': 'requires-internal-data', 'evidence': evidence}],
        'sources': [{'id': 'framework', 'title': 'Value metrics', 'publisher': 'ProductLed', 'url': 'https://productled.com/blog/value-metrics-for-product-led-growth', 'accessed': '2026-11-16'}],
    }


def entry_strategy_example():
    return {
        'summary': 'Evaluate the service before paying.',
        'models': [{'id': 'trial', 'name': 'Free trial', 'definition': 'Time-limited evaluation.',
                    'bestFit': 'Independent setup.', 'conversion': 'Choose a paid plan.', 'limits': 'The evaluation expires.'}],
        'examples': [],
        'evidence': {'kind': 'illustrative', 'note': 'Fictional entry strategy.', 'sourceIds': []}}


def entry_offer_example():
    return {
        'modelIds': ['trial'], 'rationale': 'Evaluate one team workflow.',
        'freemiumFit': 'A separate packaging decision.', 'trialFit': 'Useful for this workflow.',
        'evaluationScope': 'One team.', 'limits': 'A defined evaluation period.',
        'paidTrigger': 'The team accepts a paid plan.',
        'conversionMetric': 'Evaluating teams that pay within 30 days divided by all evaluating teams.',
        'evidence': {'kind': 'illustrative', 'note': 'Proposed measure, not a benchmark.', 'sourceIds': []}}


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links, self.scripts, self.text = [], [], [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs['href'])
        if tag == 'script':
            self.scripts.append(attrs)

    def handle_data(self, text):
        self.text.append(text)


class ValueGrowth(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='value growth ')
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / 'data project'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('PRODUCTSCAPES_')}
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'
        self.command(CLI, 'new', 'example', '--group', 'sample', '--project', self.project)
        self.domain = self.project / '_config/product-domains/sample/example'
        self.source = self.domain / 'business/value-growth.json'
        self.page = self.project / 'docs/sample/example/value-growth/index.html'
        self.model = example()

    def command(self, script, *args, ok=True):
        result = subprocess.run([sys.executable, str(script), *map(str, args)], env=self.env,
                                cwd=self.project.parent, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def write(self):
        self.source.write_text(json.dumps(self.model), encoding='utf-8')

    def test_ready_model_builds_with_menu_sources_and_unchanged_source(self):
        self.write()
        before = snapshot(self.project / '_config')
        self.command(CLI, 'validate', 'example', '--strict-ids', '--project', self.project)
        self.command(CLI, 'build', 'example', '--project', self.project)
        self.assertEqual(snapshot(self.project / '_config'), before)
        raw = self.page.read_text()
        page = Page(raw)
        self.assertEqual(len(page.ids), len(set(page.ids)))
        for link in page.links:
            if link.startswith('#'):
                self.assertIn(link[1:], page.ids)
        self.assertIn('EUR 48,000', raw)  # 10% of SAM, not 10% of TAM.
        self.assertIn('Fictional service for contract tests.', raw)
        self.assertNotRegex(raw, r'\$\{(?:title|content|app_style|app_script|market_data|domain_name)\}')
        for section in ('value', 'selling', 'activation', 'market', 'economics', 'sources'):
            self.assertIn('tab_' + section, page.ids)
            self.assertIn('tab_content_' + section, page.ids)
        home = (self.page.parent.parent / 'start/index.html').read_text()
        self.assertIn('"link": "../value-growth/index.html"', home)
        self.assertIn('"category": "Business"', home)
        self.assertTrue((self.page.parent / 'icons/logo.svg').is_file())

    def test_old_domains_and_drafts_have_an_honest_empty_page(self):
        for missing in (False, True):
            if missing:
                self.source.unlink()
            self.command(CLI, 'build', 'example', '--sections', 'value-growth', '--project', self.project)
            raw = self.page.read_text()
            self.assertIn('Value &amp; Growth is not yet documented', raw.replace('Value & Growth', 'Value &amp; Growth'))
            self.assertNotIn('id="market-form"', raw)

    def test_market_math_handles_zero_and_uses_sam_for_som(self):
        scenario = self.model['market']['scenarios'][0]
        self.assertEqual(market_totals(scenario), {'tam': 1200000, 'sam': 480000, 'som': 48000})
        self.assertEqual(market_totals({**scenario, 'serviceableShare': 0}), {'tam': 1200000, 'sam': 0, 'som': 0})

    def test_entry_models_render_safe_links_and_preserve_source(self):
        self.model['entryStrategy'] = entry_strategy_example()
        self.model['segments'][0]['activation']['entryOffer'] = entry_offer_example()
        attack = '<img src=x onerror=alert(1)>'
        self.model['entryStrategy']['models'][0]['definition'] = attack
        self.model['segments'][0]['activation']['entryOffer']['limits'] = attack
        self.write()
        before = snapshot(self.project / '_config')
        self.command(GENERATOR, '--domain-dir', self.domain)
        self.assertEqual(snapshot(self.project / '_config'), before)
        raw = self.page.read_text()
        page = Page(raw)
        self.assertIn('entry-model-trial', page.ids)
        self.assertIn('entry-offer-teams', page.ids)
        self.assertIn('#entry-model-trial', page.links)
        self.assertEqual(len(page.ids), len(set(page.ids)))
        self.assertIn(attack, page.text)
        self.assertNotIn(attack, raw)
        self.assertIn(self.model['segments'][0]['activation']['entryOffer']['conversionMetric'], page.text)
        for link in page.links:
            if link.startswith('#'):
                self.assertIn(link[1:], page.ids)

    def test_entry_model_references_and_evidence_are_validated(self):
        self.model['entryStrategy'] = entry_strategy_example()
        self.model['segments'][0]['activation']['entryOffer'] = entry_offer_example()
        self.assertEqual(validate_value_growth(self.model, 'example', self.domain), [])
        cases = []
        unknown = deepcopy(self.model)
        unknown['segments'][0]['activation']['entryOffer']['modelIds'] = ['missing-model']
        cases.append((unknown, 'missing-model'))
        missing_strategy = deepcopy(self.model)
        del missing_strategy['entryStrategy']
        cases.append((missing_strategy, 'unknown entry model'))
        incomplete = deepcopy(self.model)
        del incomplete['segments'][0]['activation']['entryOffer']['paidTrigger']
        cases.append((incomplete, 'paidTrigger'))
        duplicate = deepcopy(self.model)
        duplicate['entryStrategy']['models'] *= 2
        cases.append((duplicate, 'duplicate ids'))
        unsupported = deepcopy(self.model)
        unsupported['segments'][0]['activation']['entryOffer']['evidence']['kind'] = 'observed'
        cases.append((unsupported, 'needs at least one source'))
        bad_example = deepcopy(self.model)
        bad_example['entryStrategy']['examples'] = [{
            'id': 'offer', 'competitorId': 'missing-provider', 'name': 'Example',
            'summary': 'A fictional offer.', 'caveat': 'Not a real offer.',
            'evidence': entry_strategy_example()['evidence']}]
        cases.append((bad_example, 'missing-provider'))
        for model, error in cases:
            with self.subTest(error=error):
                self.assertIn(error, '\n'.join(validate_value_growth(model, 'example', self.domain)))

    def test_draft_entry_strategy_renders_without_segments_or_framework(self):
        self.model = {'schemaVersion': '1.0', 'domainId': 'example', 'status': 'draft',
                      'title': 'Value & Growth', 'entryStrategy': entry_strategy_example()}
        self.write()
        self.command(GENERATOR, '--domain-dir', self.domain)
        page = Page(self.page.read_text())
        self.assertIn('tab_activation', page.ids)
        self.assertIn('entry-model-trial', page.ids)
        self.assertNotIn('tab_selling', page.ids)

    def test_invalid_evidence_inputs_dates_and_duplicate_ids_are_rejected(self):
        cases = []
        for key, value in [('units', -1), ('revenuePerUnit', float('inf')), ('serviceableShare', 1.01), ('obtainableShare', -0.1), ('currency', 'javascript'), ('horizonYears', 0)]:
            model = deepcopy(self.model)
            model['market']['scenarios'][0][key] = value
            cases.append(model)
        for url in ('javascript:alert(1)', 'https://user:password@example.com/', 'https:///broken', 'https://example.com:bad/'):
            model = deepcopy(self.model)
            model['sources'][0]['url'] = url
            cases.append(model)
        model = deepcopy(self.model)
        model['segments'][0]['evidence'] = {'kind': 'observed', 'note': 'Unsupported.', 'sourceIds': ['missing']}
        cases.append(model)
        model = deepcopy(self.model)
        model['updated'] = '2026-02-30'
        cases.append(model)
        model = deepcopy(self.model)
        model['segments'].append(model['segments'][0])
        cases.append(model)
        model = deepcopy(self.model)
        model['sources'][0]['accessed'] = 'yesterday'
        cases.append(model)
        for model in cases:
            with self.subTest(model=model):
                self.assertTrue(validate_value_growth(model, 'example', self.domain))
        self.assertEqual(validate_value_growth(self.model, 'example', self.domain), [])

    def test_references_include_job_and_kpi_ownership(self):
        people = [{'group': 'Teams', 'customers': [
            {'id': 'a', 'jobsToBeDone': [{'id': 'job-a'}], 'kpiPyramids': {'top': {'id': 'kpi-a'}}},
            {'id': 'b', 'jobsToBeDone': [{'id': 'job-b'}], 'kpiPyramids': {'top': {'id': 'kpi-b'}}}]}]
        (self.domain / 'customers/customers.json').write_text(json.dumps(people))
        s = self.model['segments'][0]
        s['customerRefs'] = [{'customerId': 'a', 'jobIds': ['job-b'], 'kpiIds': ['kpi-b']}]
        s['productIds'] = ['missing-product']
        s['competitorIds'] = ['missing-player']
        errors = '\n'.join(validate_value_growth(self.model, 'example', self.domain))
        for ref in ('job-b', 'kpi-b', 'missing-product', 'missing-player'):
            self.assertIn(ref, errors)
        s['customerRefs'][0].update(jobIds=['job-a'], kpiIds=['kpi-a'])
        s['productIds'], s['competitorIds'] = [], []
        self.assertEqual(validate_value_growth(self.model, 'example', self.domain), [])

    def test_invalid_model_preserves_existing_site_in_cli_and_direct_generator(self):
        self.page.parent.mkdir(parents=True)
        self.page.write_text('Previous model')
        home = self.page.parent.parent / 'start/index.html'
        home.parent.mkdir()
        home.write_text('Previous home')
        self.model['segments'][0]['competitorIds'] = ['unknown']
        self.write()
        before = snapshot(self.project / 'docs')
        self.command(CLI, 'build', 'example', '--sections', 'value-growth', 'start', '--project', self.project, ok=False)
        self.command(GENERATOR, '--domain-dir', self.domain, ok=False)
        self.assertEqual(snapshot(self.project / 'docs'), before)

    def test_authored_text_cannot_escape_html_or_json_scripts(self):
        self.write()
        self.command(GENERATOR, '--domain-dir', self.domain)
        expected_scripts = len(Page(self.page.read_text()).scripts)
        attack = '</script><script>alert(1)</script> & ${title}'
        self.model['summary'] = attack
        self.model['market']['scenarios'][0]['name'] = attack
        self.write()
        self.command(GENERATOR, '--domain-dir', self.domain)
        raw = self.page.read_text()
        page = Page(raw)
        self.assertEqual(len(page.scripts), expected_scripts)
        self.assertIn(attack, page.text)
        self.assertNotIn('</script><script>alert(1)', raw)
        self.assertIn('\\u003c/script>', raw)


if __name__ == '__main__':
    unittest.main()
