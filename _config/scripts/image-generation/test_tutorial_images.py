"""Verify scope, resume behavior, and provider requests without live image calls."""
import base64
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import generate_tutorial_images_gemini_nanobanana_api as illustrations

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class TutorialImages(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='tutorial illustrations ')
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        previous_project = illustrations.project_paths.PROJECT_ROOT
        self.addCleanup(illustrations.project_paths.configure, previous_project)
        self.source = self.project / '_config/product-domains/sample/alpha/tutorial/tutorial.json'
        self.payload = {
            'schemaVersion': '1.0', 'domainId': 'alpha', 'status': 'draft', 'title': 'Borrowing tools',
            'audience': 'Adults new to lending libraries.',
            'concepts': [
                {'term': 'Reservation', 'meaning': 'A booking for later.',
                 'example': 'Maya books a drill for Tuesday.', 'whyItMatters': 'A booking is not collection.',
                 'illustrationPrompt': 'Show a calendar and a drill, with no money.'},
                {'term': 'Loan', 'meaning': 'Temporary borrowing.',
                 'example': 'Maya collects the drill.', 'whyItMatters': 'It must be returned.'},
            ],
        }
        self.write()
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def write(self):
        self.source.parent.mkdir(parents=True, exist_ok=True)
        self.source.write_text(json.dumps(self.payload))

    def read(self):
        return json.loads(self.source.read_text())

    def args(self, *extra):
        return illustrations.parse_args(['--project', str(self.project), *extra])

    def snapshot(self):
        return {str(path.relative_to(self.project)): path.read_bytes()
                for path in self.project.rglob('*') if path.is_file()}

    def image(self, filename='concept-reservation.png'):
        path = self.source.parent / 'media' / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG)
        return path

    def add_overview_content(self):
        self.payload['participants'] = [
            {'name': 'Borrower', 'role': 'Borrows tools from the library.', 'caresAbout': 'Having a working drill.'},
            {'name': 'Library staff', 'role': 'Check tools and lend them.', 'caresAbout': 'Safe tools returned on time.'}]
        self.payload['walkthrough'] = {
            'title': 'Maya borrows a drill', 'setup': 'Maya needs a drill for one afternoon.',
            'steps': [{'title': 'Book the drill', 'whatHappens': 'Maya reserves a drill for Tuesday.',
                       'whyItMatters': 'The staff can prepare it.', 'watchOut': 'The drill could need repairs.'},
                      {'title': 'Borrow and return it', 'whatHappens': 'Maya borrows the drill, then returns it.',
                       'whyItMatters': 'Another borrower can use it.'}],
            'outcome': 'The shelf is fitted and the drill is available again.'}

    def test_overviews_use_authored_roles_and_steps_and_concept_selection_stays_scoped(self):
        self.add_overview_content()
        self.assertEqual(len(illustrations.build_targets_for_file(self.source, self.payload)), 2)
        self.payload['participantsOverview'] = {'illustrationPrompt': 'Map the borrower and the library staff.'}
        self.payload['walkthrough']['illustrationPrompt'] = 'Show booking, borrowing, and returning with one repair setback.'
        self.write()
        targets = illustrations.build_targets_for_file(self.source, self.payload)
        self.assertEqual([target.key for target in targets],
                         ['reservation', 'loan', 'walkthrough-overview', 'participants-overview'])
        for value in ('Book the drill', 'The drill could need repairs.', self.payload['walkthrough']['outcome']):
            self.assertIn(value, targets[2].prompt)
        for value in ('Borrower', 'Library staff', 'Safe tools returned on time.'):
            self.assertIn(value, targets[3].prompt)
        with patch.object(illustrations, 'call_gemini_nanobanana_api',
                          return_value=illustrations.GeneratedImage(PNG, 'png')) as api:
            illustrations.run_generation(self.args('--concept', 'Reservation'), 'test-key')
            api.assert_called_once()
        self.assertNotIn('media', self.read()['walkthrough'])
        self.assertNotIn('media', self.read()['participantsOverview'])

    def test_explicit_participant_map_attaches_only_after_an_image_exists(self):
        self.add_overview_content()
        self.write()
        before = self.snapshot()
        with patch.object(illustrations, 'call_gemini_nanobanana_api') as api:
            illustrations.run_generation(self.args('--section', 'participants', '--dry-run'), '')
            illustrations.run_generation(self.args('--section', 'participants', '--json-only'), '')
            api.assert_not_called()
        self.assertEqual(before, self.snapshot())
        self.assertNotIn('participantsOverview', self.read())
        with patch.object(illustrations, 'call_gemini_nanobanana_api',
                          return_value=illustrations.GeneratedImage(PNG, 'png')) as api:
            illustrations.run_generation(self.args('--section', 'participants'), 'test-key')
            api.assert_called_once()
        updated = self.read()
        self.assertEqual(updated['participantsOverview']['media'][0]['src'], 'media/participants-overview.png')
        del updated['participantsOverview']
        self.assertEqual(updated, self.payload)
        self.assertEqual(illustrations.validate_tutorial(self.read(), 'alpha', self.source.parent), [])

    def test_walkthrough_failure_resumes_its_own_media_without_touching_concepts(self):
        self.add_overview_content()
        self.write()
        with patch.object(illustrations, 'call_gemini_nanobanana_api', side_effect=RuntimeError('busy')):
            with self.assertRaisesRegex(RuntimeError, 'busy'):
                illustrations.run_generation(self.args('--section', 'walkthrough'), 'test-key')
        self.assertEqual(self.read(), self.payload)
        self.image('walkthrough-overview.webp')  # Recover a file saved by an earlier interrupted run.
        with patch.object(illustrations, 'call_gemini_nanobanana_api') as api:
            illustrations.run_generation(self.args('--section', 'walkthrough', '--json-only'), '')
            self.assertEqual(self.read()['walkthrough']['media'][0]['src'], 'media/walkthrough-overview.webp')
            before = self.snapshot()
            illustrations.run_generation(self.args('--section', 'walkthrough'), '')
            self.assertEqual(before, self.snapshot())
            api.assert_not_called()
        updated = self.read()
        del updated['walkthrough']['media']
        self.assertEqual(updated, self.payload)

    def test_prompt_explains_the_specific_concept_for_the_intended_reader(self):
        target = illustrations.build_targets_for_file(self.source, self.payload)[0]
        for value in ('Adults new to lending libraries.', 'Maya books a drill for Tuesday.',
                      'A booking is not collection.', 'Show a calendar and a drill, with no money.', '16:9'):
            self.assertIn(value, target.prompt)
        self.assertEqual(target.image_path.name, 'concept-reservation.png')

    def test_dry_run_and_empty_scope_need_no_key_and_make_no_writes(self):
        before = self.snapshot()
        with patch.object(illustrations, 'call_gemini_nanobanana_api') as api:
            self.assertEqual(illustrations.run_generation(self.args('--dry-run', '--limit', '1', '--show-prompts'), ''), 0)
            self.assertIn('Would generate 1', self.output.getvalue())
            self.assertEqual(self.snapshot(), before)
            self.source.unlink()
            self.assertEqual(illustrations.run_generation(self.args(), ''), 0)
            api.assert_not_called()

    def test_missing_key_fails_before_writing(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'GEMINI_API_KEY'):
            illustrations.run_generation(self.args(), '')
        self.assertEqual(before, self.snapshot())

    def test_json_only_recovers_other_formats_preserves_other_media_and_is_idempotent(self):
        self.payload['concepts'][0]['media'] = [
            {'type': 'image', 'src': 'media/manual.png', 'alt': 'A hand-drawn example.'}]
        self.write()
        self.image('manual.png')
        self.image('concept-reservation.webp')
        with patch.object(illustrations, 'call_gemini_nanobanana_api') as api:
            illustrations.run_generation(self.args('--json-only'), '')
            media = self.read()['concepts'][0]['media']
            self.assertEqual(media[0], self.payload['concepts'][0]['media'][0])
            self.assertEqual(media[1]['src'], 'media/concept-reservation.webp')
            self.assertNotIn('media', self.read()['concepts'][1])
            before = self.snapshot()
            illustrations.run_generation(self.args('--json-only'), '')
            self.assertEqual(self.snapshot(), before)
            api.assert_not_called()

    def test_failure_checkpoints_success_and_resumes_without_duplicate_media(self):
        result = illustrations.GeneratedImage(PNG, 'png')
        with patch.object(illustrations, 'call_gemini_nanobanana_api', side_effect=[result, RuntimeError('busy')]):
            with self.assertRaisesRegex(RuntimeError, 'busy'):
                illustrations.run_generation(self.args(), 'test-key')
        first, second = self.read()['concepts']
        self.assertEqual(first['media'][0]['src'], 'media/concept-reservation.png')
        self.assertNotIn('media', second)
        self.assertIn('Maya books a drill', (self.source.parent / 'media/concept-reservation.prompt.txt').read_text())
        with patch.object(illustrations, 'call_gemini_nanobanana_api', return_value=result) as api:
            illustrations.run_generation(self.args(), 'test-key')
            self.assertEqual(api.call_count, 1)
            self.assertEqual(api.call_args.args[1].key, 'loan')
        self.assertTrue(all(len(concept['media']) == 1 for concept in self.read()['concepts']))
        before = self.snapshot()
        illustrations.run_generation(self.args('--skip-existing'), '')
        self.assertEqual(before, self.snapshot())

    def test_overwrite_keeps_reviewed_alt_and_caption_and_respects_response_format(self):
        self.image()
        self.payload['concepts'][0]['media'] = [{
            'id': illustrations.MEDIA_ID, 'type': 'image', 'src': 'media/concept-reservation.png',
            'alt': 'Reviewed visual description.', 'caption': 'Reviewed teaching point.'}]
        self.write()
        with patch.object(illustrations, 'call_gemini_nanobanana_api',
                          return_value=illustrations.GeneratedImage(b'JPEG test bytes', 'jpg')) as api:
            illustrations.run_generation(self.args('--overwrite', '--concept', 'Reservation'), 'test-key')
            api.assert_called_once()
        media = self.read()['concepts'][0]['media'][0]
        self.assertEqual(media['src'], 'media/concept-reservation.jpg')
        self.assertEqual(media['alt'], 'Reviewed visual description.')
        self.assertEqual(media['caption'], 'Reviewed teaching point.')

    def test_limit_is_global_across_domains_and_unselected_concepts_are_unchanged(self):
        other = self.project / '_config/product-domains/another/beta/tutorial/tutorial.json'
        other.parent.mkdir(parents=True)
        other_payload = deepcopy(self.payload)
        other_payload['domainId'] = 'beta'
        other.write_text(json.dumps(other_payload))
        with patch.object(illustrations, 'call_gemini_nanobanana_api',
                          return_value=illustrations.GeneratedImage(PNG, 'png')) as api:
            illustrations.run_generation(self.args('--limit', '1'), 'test-key')
            api.assert_called_once()
        self.assertEqual(self.read()['concepts'][1], self.payload['concepts'][1])
        self.assertEqual(json.loads(other.read_text()), other_payload)

    def test_selection_and_reordering_keep_names_and_do_not_call_for_existing_images(self):
        self.image()
        self.payload['concepts'].reverse()
        self.write()
        args = illustrations.parse_args(['--domain-dir', str(self.source.parents[1]), '--concept', 'reservation'])
        with patch.object(illustrations, 'call_gemini_nanobanana_api') as api:
            illustrations.run_generation(args, '')
            api.assert_not_called()
        self.assertNotIn('media', self.read()['concepts'][0])
        self.assertEqual(self.read()['concepts'][1]['media'][0]['src'], 'media/concept-reservation.png')
        with self.assertRaisesRegex(ValueError, 'No concept matches'):
            illustrations.run_generation(self.args('--concept', 'Unknown'), '')

    def test_colliding_terms_and_symlink_escapes_fail_before_calls(self):
        self.payload['concepts'][1]['term'] = 'Reservation!'
        self.write()
        with self.assertRaisesRegex(ValueError, 'same filename key'):
            illustrations.run_generation(self.args(), 'test-key')
        self.payload['concepts'][1]['term'] = 'Loan'
        self.write()
        outside = self.project / 'outside'
        outside.mkdir()
        (self.source.parent / 'media').symlink_to(outside, target_is_directory=True)
        with patch.object(illustrations, 'call_gemini_nanobanana_api') as api:
            with self.assertRaisesRegex(ValueError, 'outside the tutorial'):
                illustrations.run_generation(self.args(), 'test-key')
            api.assert_not_called()
        self.assertEqual(list(outside.iterdir()), [])

    def test_concurrent_prose_edit_is_preserved_after_a_slow_response(self):
        def edit_during_call(*_):
            self.payload['title'] = 'Newer authored title'
            self.write()
            return illustrations.GeneratedImage(PNG, 'png')
        with patch.object(illustrations, 'call_gemini_nanobanana_api', side_effect=edit_during_call):
            with self.assertRaisesRegex(RuntimeError, 'Tutorial changed during generation'):
                illustrations.run_generation(self.args('--limit', '1'), 'test-key')
        self.assertEqual(self.read(), self.payload)
        self.assertTrue((self.source.parent / 'media/concept-reservation.png').is_file())

    def test_api_uses_landscape_header_auth_and_retries_transient_failures(self):
        target = illustrations.build_targets_for_file(self.source, self.payload)[0]
        response = json.dumps({'candidates': [{'content': {'parts': [
            {'thought': True, 'inlineData': {'mimeType': 'image/png', 'data': 'dGhvdWdodA=='}},
            {'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(PNG).decode()}},
        ]}}]}).encode()
        busy = urllib.error.HTTPError('https://example.invalid', 429, 'Rate limit', {}, io.BytesIO(b'retry'))
        with patch.object(illustrations.urllib.request, 'urlopen', side_effect=[busy, io.BytesIO(response)]) as call, \
             patch.object(illustrations.time, 'sleep') as sleep:
            image = illustrations.call_gemini_nanobanana_api('test-secret', target,
                         self.args('--max-retries', '1', '--retry-delay-seconds', '0'))
            self.assertEqual(image.image_bytes, PNG)
            request = call.call_args.args[0]
            self.assertNotIn('test-secret', request.full_url)
            self.assertEqual(request.get_header('X-goog-api-key'), 'test-secret')
            config = json.loads(request.data)['generationConfig']
            self.assertEqual(config['imageConfig'], {'aspectRatio': '16:9', 'imageSize': '1K'})
            sleep.assert_called_once_with(0)
        failure = urllib.error.HTTPError('https://example.invalid', 400, 'Bad request', {}, io.BytesIO(b'test-secret'))
        with patch.object(illustrations.urllib.request, 'urlopen', side_effect=failure) as call:
            with self.assertRaisesRegex(RuntimeError, r'Gemini API error 400: \[redacted\]'):
                illustrations.call_gemini_nanobanana_api('test-secret', target, self.args())
            call.assert_called_once()


if __name__ == '__main__':
    unittest.main()
