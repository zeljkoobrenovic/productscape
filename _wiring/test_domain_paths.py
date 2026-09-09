"""Offline regression checks: python3 -B -m unittest discover -s _wiring."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from domain_paths import discover_domain_dirs, domain_docs_path, list_domain_files, resolve_domain_dir


class GroupedDomainTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='productscape-domain-paths-')
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.root = self.repo / '_config' / 'product-domains'
        self.root.mkdir(parents=True)

    def make_domain(self, group, domain_id, registered=True):
        domain = self.root / group / domain_id
        domain.mkdir(parents=True)
        if registered:
            (domain / 'start').mkdir()
            (domain / 'start' / 'config.json').write_text(json.dumps({
                'id': domain_id, 'name': "A domain's name", 'description': 'A multiline\ndescription',
            }))
        return domain

    def test_discovers_arbitrary_groups_and_skips_shared_navigation(self):
        second = self.make_domain('new-group', 'second')
        first = self.make_domain('another-group', 'first')
        (self.root / 'start' / 'icons').mkdir(parents=True)
        (self.root / 'start' / 'apps.json').write_text('{}')
        (self.root / 'empty-group').mkdir()
        (self.root / '.hidden' / 'ignored').mkdir(parents=True)
        self.assertEqual(discover_domain_dirs(self.root), [first, second])

    def test_moving_a_domain_keeps_its_id_resolvable(self):
        domain = self.make_domain('old-group', 'example')
        self.assertEqual(domain_docs_path('example', 'start/index.html', domains_root=self.root), 'old-group/example/start/index.html')
        (self.root / 'new-group').mkdir()
        moved = domain.rename(self.root / 'new-group' / domain.name)
        self.assertEqual(resolve_domain_dir('example', self.root), moved)
        self.assertEqual(domain_docs_path('example', 'start/index.html', domains_root=self.root), 'new-group/example/start/index.html')

    def test_duplicate_ids_are_rejected_across_groups(self):
        self.make_domain('one', 'example')
        self.make_domain('two', 'example')
        with self.assertRaisesRegex(ValueError, 'Duplicate domain ID'):
            resolve_domain_dir('example', self.root)

    def test_flat_domains_are_rejected(self):
        domain = self.make_domain('group', 'example')
        domain.rename(self.root / 'example')
        with self.assertRaisesRegex(ValueError, 'directly under'):
            discover_domain_dirs(self.root)

    def test_group_names_and_missing_ids_do_not_resolve_as_domains(self):
        self.make_domain('group', 'example')
        for domain_id in ('group', 'missing', '../example', 'group/example'):
            with self.subTest(domain_id=domain_id), self.assertRaisesRegex(ValueError, 'Unknown domain'):
                resolve_domain_dir(domain_id, self.root)

    def test_artifact_discovery_and_incomplete_domains(self):
        complete = self.make_domain('one', 'complete')
        incomplete = self.make_domain('two', 'incomplete', registered=False)
        self.assertEqual(discover_domain_dirs(self.root), [complete, incomplete])
        self.assertEqual(list_domain_files('start/config.json', domains_root=self.root), [complete / 'start/config.json'])
        self.assertEqual(list_domain_files('start/config.json', 'incomplete', self.root), [])
        self.assertEqual(list_domain_files('start/config.json', 'complete', self.root), [complete / 'start/config.json'])

    def test_grouped_domain_validation_still_loads_shared_schemas(self):
        domain = self.make_domain('arbitrary-group', 'example')
        repo = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            'grouped_domain_validator', repo / 'skills/scripts/validate-domain-model.py'
        )
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        errors = []
        validator.validate_against_schema(domain, domain / 'start/config.json', {'id': 123}, errors)
        self.assertTrue(errors, 'Invalid data must not bypass the shared schema after a domain moves.')

    def test_residuality_composite_ids_remain_lowercase_and_scoped(self):
        repo = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('composite_validator', repo / 'skills/scripts/validate-domain-model.py')
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        payload = {'stressors': [{'impacts': [{'targetId': 'customer/job/step'}]}]}
        errors = []
        validator.validate_lowercase_ids(self.repo, payload, errors, composite_targets=True)
        self.assertEqual(errors, [])
        validator.validate_lowercase_ids(self.repo, payload, errors)
        self.assertTrue(errors, 'Simple IDs elsewhere must still reject slashes.')
        payload['stressors'][0]['impacts'][0]['targetId'] = 'Customer/job'
        errors = []
        validator.validate_lowercase_ids(self.repo, payload, errors, composite_targets=True)
        self.assertTrue(any('not lowercase' in error for error in errors))

    def install_wrappers(self, failed_domain=None):
        wiring = self.repo / '_wiring'
        scripts = wiring / 'product-domains'
        scripts.mkdir(parents=True)
        source = Path(__file__).resolve().parent
        shutil.copy2(source / 'domain_paths.py', wiring)
        shutil.copy2(source / 'project_paths.py', wiring)
        shutil.copy2(source / 'tutorial_model.py', wiring)
        shutil.copy2(source.parent / 'productscapes.py', self.repo)
        (self.repo / 'skills/scripts').mkdir(parents=True)
        shutil.copy2(source.parent / 'skills/scripts/schema_check.py', self.repo / 'skills/scripts')
        (self.repo / '_config/_schema').mkdir(parents=True)
        shutil.copy2(source.parent / '_config/_schema/tutorial.schema.json', self.repo / '_config/_schema')
        shutil.copytree(source.parent / '_templates/catalog', self.repo / '_templates/catalog')
        (self.repo / '_config/_shared').mkdir(parents=True)
        navigation = self.root / 'start/apps.json'
        navigation.parent.mkdir()
        shutil.copy2(source.parent / '_config/product-domains/start/apps.json', navigation)
        for section in ('start', 'customers', 'product-deployments', 'product-bricks', 'teams', 'competition', 'residuality', 'tutorial', 'evidence-explorer'):
            template = self.repo / '_templates' / section / 'index.html'
            template.parent.mkdir(parents=True)
            template.write_text('stub template')
        (self.repo / 'docs').mkdir()
        for domain in discover_domain_dirs(self.root):
            for seed in (source.parent / '_templates/domain').rglob('*.json'):
                target = domain / seed.relative_to(source.parent / '_templates/domain')
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(seed.read_text().replace('__DOMAIN_ID__', domain.name))
        evidence = wiring / 'evidence-explorer'
        evidence.mkdir()
        (evidence / 'generate-evidence-explorer-docs.py').write_text('pass')
        shutil.copy2(source / 'product-domains/run.sh', scripts)
        for name in ('start', 'customers', 'products', 'product-bricks', 'teams', 'competition', 'residuality', 'tutorial'):
            (scripts / f'generate-{name}-docs.py').write_text(
                'import json, sys\n'
                f'with open({str(scripts / "calls.jsonl")!r}, "a") as output:\n'
                '    output.write(json.dumps(sys.argv) + "\\n")\n'
                f'if sys.argv[1] == {failed_domain!r}:\n'
                '    sys.exit(1)\n'
            )
        return scripts

    def test_wrappers_discover_groups_and_preserve_metadata(self):
        for group, domain_id in (('new-group', 'first'), ('another-group', 'second')):
            self.make_domain(group, domain_id)
        scripts = self.install_wrappers()
        for arguments, expected_ids in (
            ([str(self.root / 'another-group/second')], ['second'] * 8),
            (['--project', str(self.repo), '--all'], ['first'] * 8 + ['second'] * 8),
        ):
            with self.subTest(arguments=arguments):
                calls = scripts / 'calls.jsonl'
                calls.write_text('')
                result = subprocess.run(['sh', str(scripts / 'run.sh'), *arguments], cwd=self.repo, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                records = [json.loads(line) for line in calls.read_text().splitlines()]
                self.assertEqual([record[1] for record in records], expected_ids)
                self.assertTrue(all(record[2:] == ["A domain's name", 'A multiline\ndescription'] for record in records))

    def test_full_wrapper_preserves_failure_isolation(self):
        self.make_domain('one', 'broken')
        self.make_domain('two', 'healthy')
        scripts = self.install_wrappers(failed_domain='broken')
        result = subprocess.run(['sh', str(scripts / 'run.sh'), '--project', str(self.repo), '--all'], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        records = [json.loads(line) for line in (scripts / 'calls.jsonl').read_text().splitlines()]
        self.assertEqual([record[1] for record in records], ['broken'] * 8 + ['healthy'] * 8)
        self.assertIn('8 failure(s)', result.stderr)

    def test_full_wrapper_fails_for_an_empty_registry(self):
        scripts = self.install_wrappers()
        result = subprocess.run(['sh', str(scripts / 'run.sh'), '--project', str(self.repo), '--all'], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('No registered domains', result.stderr)


if __name__ == '__main__':
    unittest.main()
