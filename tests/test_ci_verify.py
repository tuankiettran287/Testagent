import unittest
import json
import io
import os
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.ci_verify import main, quality_gate, validate_browser_evidence


class CiGateTests(unittest.TestCase):
    def test_zero_discovered_tests_cannot_pass(self):
        self.assertFalse(quality_gate(0, unittest.TestResult()))

    def test_selected_but_unexecuted_tests_cannot_pass(self):
        self.assertFalse(quality_gate(3, unittest.TestResult()))

    def test_skip_is_visible_and_fails_ci_even_if_unittest_is_successful(self):
        result = unittest.TestResult()
        result.testsRun = 1
        result.skipped.append(('browser-test', 'Chromium missing'))
        self.assertTrue(result.wasSuccessful())
        self.assertFalse(quality_gate(1, result))

    def test_expected_failure_is_not_counted_as_pass(self):
        result = unittest.TestResult()
        result.testsRun = 1
        result.expectedFailures.append(('oracle', 'known defect'))
        self.assertFalse(quality_gate(1, result))

    def test_executed_successful_nonempty_suite_passes(self):
        result = unittest.TestResult()
        result.testsRun = 3
        self.assertTrue(quality_gate(3, result))


class EvidenceGateTests(unittest.TestCase):
    def bundle(self, directory):
        path = Path(directory) / 'fixture'
        artifacts = path / 'artifacts' / 'run-1'
        artifacts.mkdir(parents=True)
        data = {'cases': [{'id': 'case-1', 'browser_case': True}],
                'runs': [{'id': 'run-1', 'status': 'COMPLETED',
                          'summary': json.dumps({'test_case_ids': ['case-1']})}],
                'results': [{'run_id': 'run-1', 'test_case_id': 'case-1',
                             'artifacts': json.dumps(['case-1.spec.ts', 'case-1-trace.zip'])}]}
        for name in ('case-1.spec.ts', 'case-1-trace.zip'):
            (artifacts / name).write_text('synthetic artifact', encoding='utf-8')
        (path / 'runs.json').write_text(json.dumps(data), encoding='utf-8')
        return path, artifacts, data

    def test_missing_trace_file_cannot_be_evidence_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            _, artifacts, _ = self.bundle(directory)
            self.assertTrue(validate_browser_evidence(Path(directory))['complete'])
            (artifacts / 'case-1-trace.zip').unlink()
            with self.assertRaisesRegex(RuntimeError, 'Missing.*artifact'):
                validate_browser_evidence(Path(directory))

    def test_reporter_from_another_run_cannot_match_current_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, data = self.bundle(directory)
            data['results'][0]['run_id'] = 'old-run'
            (path / 'runs.json').write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'mismatched run'):
                validate_browser_evidence(Path(directory))

    def test_failure_in_post_execution_checks_cannot_leave_a_green_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            suite = unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])
            with patch('sys.argv', ['ci_verify', '--output', directory]), \
                 patch('scripts.ci_verify.browser_runner_available', return_value=True), \
                 patch('scripts.ci_verify.unittest.defaultTestLoader.discover', return_value=suite), \
                 patch('scripts.ci_verify.benchmark', side_effect=RuntimeError('Broken benchmark')), \
                 patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''}), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 1)
            report = json.loads((Path(directory) / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(report['outcome'], 'RUN-FAILED')
            self.assertIn('Broken benchmark', report['error'])
