import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import ci_agent_cases


class FunctionalCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = ci_agent_cases.load_catalog()

    def reject_catalog(self, catalog, message):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cases.json'
            path.write_text(json.dumps(catalog), encoding='utf-8')
            with patch.object(ci_agent_cases, 'CATALOG', path):
                with self.assertRaisesRegex(ValueError, message):
                    ci_agent_cases.load_catalog()

    def test_removing_a_registered_function_cannot_silently_reduce_coverage(self):
        self.catalog['cases'].pop(0)
        self.reject_catalog(self.catalog, 'every registered agent function')

    def test_duplicate_case_ids_cannot_mask_an_unexecuted_case(self):
        self.catalog['cases'][1]['id'] = self.catalog['cases'][0]['id']
        self.reject_catalog(self.catalog, 'unique IDs')

    def test_unknown_scenario_cannot_be_accepted_as_an_executable_case(self):
        self.catalog['cases'][-1]['scenario'] = 'not_implemented'
        self.reject_catalog(self.catalog, 'every reviewed contract scenario')

    def test_missing_oracle_cannot_enter_the_reviewed_catalog(self):
        self.catalog['cases'][0]['expected'] = []
        self.reject_catalog(self.catalog, 'Incomplete reviewed case')

    def test_evidence_failure_after_passing_cases_must_fail_the_run(self):
        fixture = Mock()
        definitions = {'cases': [{'id': 'CASE-1', 'title': 'A passing scenario',
                                  'scenario': 'manual_rejected', 'steps': ['Act'], 'expected': ['Verify']}]}
        fixture.api_events = []
        fixture.calls = []
        with tempfile.TemporaryDirectory() as directory:
            with patch('sys.argv', ['ci_agent_cases', '--output', directory]), \
                 patch.object(ci_agent_cases, 'load_catalog', return_value=copy.deepcopy(definitions)), \
                 patch.object(ci_agent_cases, 'FunctionalChecks') as factory, \
                 patch.dict(ci_agent_cases.SCENARIOS, {'manual_rejected': lambda checks: None}), \
                 patch.object(ci_agent_cases, 'validate_browser_evidence', side_effect=RuntimeError('Missing trace')), \
                 patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''}), redirect_stdout(io.StringIO()):
                factory.return_value.__enter__.return_value = fixture
                self.assertEqual(ci_agent_cases.main(), 1)
            report = json.loads((Path(directory) / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(report['outcome'], 'RUN-FAILED')
            self.assertEqual(report['passed'], 1)
            self.assertIn('Missing trace', report['error'])
