import copy
import unittest

from scripts.verify_playwright_report import case_results


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
