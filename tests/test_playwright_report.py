import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.ci_agent_cases import load_catalog
from scripts.verify_playwright_report import case_results, demo_results, main, select_cases, suite_results


class PlaywrightReportTests(unittest.TestCase):
    def setUp(self):
        self.definitions = [{'id': 'AGENT-F01', 'title': 'Routing', 'function': 'orchestrator'}]
        self.spec = {'title': 'AGENT-F01 Routing', 'tests': [
            {'expectedStatus': 'passed', 'results': [{'status': 'passed', 'duration': 123}]}]}

    def rows(self, spec=None):
        return case_results({'suites': [{'specs': [spec or self.spec]}]}, self.definitions)

    def test_native_failure_preserves_error_in_the_case_result(self):
        self.spec['tests'][0]['results'][0].update(status='failed', errors=[{'message': 'Expected 200, received 500'}])
        self.assertEqual(self.rows()[0]['status'], 'FAIL')
        self.assertIn('received 500', self.rows()[0]['detail'])

    def test_missing_case_is_not_executed_or_passed(self):
        rows = case_results({'suites': []}, self.definitions)
        self.assertEqual(rows[0]['status'], 'NOT_RUN')

    def test_skip_and_expected_failure_cannot_be_a_pass(self):
        self.spec['tests'][0]['results'][0]['status'] = 'skipped'
        self.assertEqual(self.rows()[0]['status'], 'SKIPPED')
        self.spec['tests'][0]['expectedStatus'] = 'failed'
        self.spec['tests'][0]['results'][0]['status'] = 'failed'
        self.assertEqual(self.rows()[0]['status'], 'ERROR')

    def test_duplicate_report_entries_cannot_hide_a_missing_case(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            case_results({'suites': [{'specs': [self.spec, copy.deepcopy(self.spec)]}]}, self.definitions)

    def test_retry_cannot_be_counted_as_a_first_pass(self):
        self.spec['tests'][0]['results'].append({'status': 'passed'})
        with self.assertRaisesRegex(ValueError, 'no retry'):
            self.rows()

    def test_nested_native_suites_are_matched_to_the_catalog_id(self):
        rows = case_results({'suites': [{'suites': [{'specs': [self.spec]}]}]}, self.definitions)
        self.assertEqual(rows[0]['test_id'], 'AGENT-F01')
        self.assertEqual(rows[0]['status'], 'PASS')
        self.assertEqual(rows[0]['duration_seconds'], 0.123)


class DemoReportTests(unittest.TestCase):
    def setUp(self):
        self.definition = {'id': 'DEMO-FLAKY01', 'expected_report_status': 'FLAKY',
                           'expected_attempts': ['failed', 'passed']}
        self.spec = {'title': 'DEMO-FLAKY01 Transient response', 'tests': [{
            'status': 'flaky', 'expectedStatus': 'passed',
            'results': [{'status': 'failed'}, {'status': 'passed'}]}]}

    def test_flaky_demo_requires_the_recorded_failed_then_passed_attempts(self):
        row = demo_results([self.spec], [self.definition])[0]
        self.assertEqual(row['status'], 'FLAKY')
        self.assertTrue(row['matches_expected_demo'])
        self.spec['tests'][0]['results'] = [{'status': 'passed'}]
        self.assertFalse(demo_results([self.spec], [self.definition])[0]['matches_expected_demo'])

    def test_missing_demo_is_not_marked_matched(self):
        row = demo_results([], [self.definition])[0]
        self.assertEqual(row['status'], 'NOT_RUN')
        self.assertFalse(row['matches_expected_demo'])

    def test_expected_failure_metadata_cannot_hide_a_real_demo_failure(self):
        self.spec['tests'][0]['expectedStatus'] = 'failed'
        row = demo_results([self.spec], [self.definition])[0]
        self.assertEqual(row['status'], 'ERROR')
        self.assertFalse(row['matches_expected_demo'])


class SuiteReportTests(unittest.TestCase):
    def test_suites_cover_all_reviewed_ids_without_overlap(self):
        catalog = load_catalog()
        functional = {case['id'] for case in select_cases(catalog, 'functional')}
        demos = {case['id'] for case in select_cases(catalog, 'status-demo')}
        self.assertEqual(len(functional), 30)
        self.assertEqual(len(demos), 7)
        self.assertFalse(functional & demos)
        self.assertEqual(functional | demos, {case['id'] for case in catalog['cases']})

    def test_results_from_the_other_job_are_rejected(self):
        catalog = load_catalog()
        for suite, foreign_id in [('functional', 'DEMO-PASS01'), ('status-demo', 'AGENT-F01')]:
            with self.subTest(suite=suite), self.assertRaisesRegex(ValueError, 'outside the selected suite'):
                suite_results({'suites': [{'specs': [{'title': f'{foreign_id} Foreign case'}]}]},
                              select_cases(catalog, suite), suite)

    def test_each_job_validates_its_own_report_without_requiring_the_other_cases(self):
        catalog = load_catalog()
        native_status = {'PASS': 'expected', 'FAIL': 'unexpected', 'FLAKY': 'flaky', 'SKIPPED': 'skipped'}
        for suite, total, outcome in [('functional', 30, 'RUN-PASSED'), ('status-demo', 7, 'RUN-FAILED')]:
            with self.subTest(suite=suite), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                definitions = select_cases(catalog, suite)
                specs = []
                for definition in definitions:
                    expected = definition.get('expected_report_status', 'PASS')
                    specs.append({'title': f"{definition['id']} {definition['title']}", 'tests': [{
                        'status': native_status[expected], 'expectedStatus': 'skipped' if expected == 'SKIPPED' else 'passed',
                        'results': [{'status': status} for status in definition.get('expected_attempts', ['passed'])]}]})
                (output / 'results.json').write_text(json.dumps({'suites': [{'specs': specs}], 'errors': []}), encoding='utf-8')
                (output / 'fixture-finalization.json').write_text(json.dumps({'cleanup': 'OWNED_FIXTURE_TEARDOWN_COMPLETED'}), encoding='utf-8')
                (output / 'html').mkdir()
                (output / 'html/index.html').touch()
                (output / 'junit.xml').touch()
                with patch('sys.argv', ['verify_playwright_report', '--suite', suite, '--output', directory]), \
                     patch('scripts.verify_playwright_report.git_output', return_value=''), \
                     patch('scripts.verify_playwright_report.validate_browser_evidence', return_value={'complete': True}), \
                     patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''}), redirect_stdout(io.StringIO()):
                    self.assertEqual(main(), 0)
                manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
                self.assertEqual(manifest['selected'], total)
                self.assertEqual(manifest['outcome'], outcome)
                self.assertEqual(manifest['validation'], 'MATCHED')
                self.assertEqual(set(manifest['selected_case_ids']), {case['id'] for case in definitions})
                self.assertEqual(len(json.loads((output / 'catalog.json').read_text(encoding='utf-8'))['cases']), total)
                self.assertNotIn('NOT_RUN', {case['status'] for case in manifest['cases']})
