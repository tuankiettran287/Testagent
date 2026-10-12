"""Execute the reviewed agent functional case catalog; never import user data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
import unittest
import uuid
from pathlib import Path

from scripts.agent_function_cases import FunctionalChecks, SCENARIOS
from scripts.ci_verify import EvidenceResult, git_output, quality_gate, validate_browser_evidence, write_junit
from testagent.skills import SKILLS


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'tests' / 'agent_function_cases.json'


class CatalogCase(unittest.TestCase):
    def __init__(self, definition, checks):
        super().__init__('runTest')
        self.definition = definition
        self.checks = checks

    def id(self):
        return self.definition['id']

    def __str__(self):
        return f"{self.id()} - {self.definition['title']}"

    def runTest(self):
        self.checks.details = {}
        before_events = len(self.checks.api_events)
        before_calls = len(self.checks.calls)
        try:
            if 'function' in self.definition:
                self.checks.check_function(self.definition['function'])
            else:
                SCENARIOS[self.definition['scenario']](self.checks)
        finally:
            self.definition['evidence'] = {
                **self.checks.details, 'fixture_model_calls': len(self.checks.calls) - before_calls,
                'api_events': self.checks.api_events[before_events:],
            }


def load_catalog():
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    cases = catalog['cases']
    ids = [case['id'] for case in cases]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Case catalog must have nonempty unique IDs')
    functions = [case['function'] for case in cases if 'function' in case]
    if len(functions) != len(set(functions)) or set(functions) != {skill.id for skill in SKILLS}:
        raise ValueError('Catalog must cover every registered agent function exactly once')
    scenarios = [case['scenario'] for case in cases if 'scenario' in case]
    if len(scenarios) != len(set(scenarios)) or set(scenarios) != set(SCENARIOS):
        raise ValueError('Catalog must select every reviewed contract scenario exactly once')
    for case in cases:
        if not case.get('steps') or not case.get('expected') or not case.get('title'):
            raise ValueError(f"Incomplete reviewed case: {case['id']}")
        if case.get('report_demo'):
            if ('function' in case or 'scenario' in case
                or case.get('expected_report_status') not in {'PASS', 'FAIL', 'FLAKY', 'SKIPPED'}
                or not case.get('expected_attempts')):
                raise ValueError(f"Invalid report demo case: {case['id']}")
            continue
        if ('function' in case) == ('scenario' in case):
            raise ValueError('Select exactly one function or contract scenario per case')
    return catalog


def write_summary(path, report):
    lines = ['## Agent test cases', '',
             f"**{report['outcome']}**: {report['executed']}/{report['selected']} executed; "
             f"{report.get('passed', 0)} passed; {report.get('failures', 0)} failures; "
             f"{report.get('flaky', 0)} flaky; {report.get('errors', 0)} errors; {report.get('skipped', 0)} skipped.", '',
             'Data is generated in a new temporary database. AI responses are fixtures; '
             'Chromium and HTTP execution are real. No workspace database, stored cases, '
             'live results or AI session is imported.', '',
             '| Case | Function / scenario | Result | Seconds |', '|---|---|---|---:|']
    for case in report['cases']:
        lines.append(f"| {case['test_id']} | {case.get('function', case.get('scenario', ''))} | "
                     f"{case['status']} | {case['duration_seconds']:.3f} |")
    if report.get('error'):
        lines.extend(['', 'Setup/evidence validation failed; inspect manifest.json and cases.log.'])
    text = '\n'.join(lines) + '\n'
    path.write_text(text, encoding='utf-8')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a', encoding='utf-8') as stream:
            stream.write(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output/aoce/agent-cases'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    evidence_path = args.output / 'browser' / uuid.uuid4().hex
    previous = os.environ.get('TESTAGENT_EVIDENCE_DIR')
    os.environ['TESTAGENT_EVIDENCE_DIR'] = str(evidence_path.resolve())
    report = {'schema_version': 'agent-functional-cases-1', 'outcome': 'BLOCKED',
              'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'run_id': os.getenv('GITHUB_RUN_ID', 'local'),
              'attempt_id': os.getenv('GITHUB_RUN_ATTEMPT', '1'),
              'trigger': os.getenv('GITHUB_EVENT_NAME', 'local'),
              'data_origin': 'generated-fixtures-only', 'workspace_data_imported': False,
              'model_mode': 'fixture', 'actual_provider_calls': 0,
              'browser_and_http_execution': 'real', 'automatic_retries': 0,
              'selected': 0, 'executed': 0, 'cases': [],
              'browser_evidence_path': str(evidence_path.relative_to(args.output)),
              'cleanup': 'NOT_STARTED'}
    try:
        report['code_revision'] = git_output('rev-parse', 'HEAD')
        report['working_tree_dirty'] = bool(git_output('status', '--porcelain'))
        report['catalog_sha256'] = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
        catalog = load_catalog()
        definitions = [case for case in catalog['cases'] if not case.get('report_demo')]
        report['selected'] = len(definitions)
        report['function_coverage'] = sorted(case['function'] for case in definitions if 'function' in case)
        (args.output / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
        with FunctionalChecks() as checks:
            suite = unittest.TestSuite(CatalogCase(case, checks) for case in definitions)
            with (args.output / 'cases.log').open('w', encoding='utf-8') as log:
                result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=EvidenceResult).run(suite)
            by_id = {case['id']: case for case in definitions}
            report.update(executed=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                          skipped=len(result.skipped), passed=sum(case['status'] == 'PASS' for case in result.cases),
                          cases=[{**by_id[item['test_id']], **item} for item in result.cases],
                          outcome='RUN-PASSED' if quality_gate(len(definitions), result) else 'RUN-FAILED')
        report['cleanup'] = 'OWNED_FIXTURE_TEARDOWN_COMPLETED'
        report['browser_evidence'] = validate_browser_evidence(evidence_path)
    except Exception:
        report['outcome'] = 'RUN-FAILED' if report['executed'] else 'BLOCKED'
        report['error'] = traceback.format_exc()
    finally:
        if previous is None:
            os.environ.pop('TESTAGENT_EVIDENCE_DIR', None)
        else:
            os.environ['TESTAGENT_EVIDENCE_DIR'] = previous
        report['duration_seconds'] = round(time.monotonic() - started, 3)
        report['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (args.output / 'cases.log').touch(exist_ok=True)
        write_junit(args.output / 'junit.xml', report)
        (args.output / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        write_summary(args.output / 'summary.md', report)
    print(f"{report['outcome']}: {report['executed']}/{report['selected']} cases executed; {args.output / 'manifest.json'}")
    return 0 if report['outcome'] == 'RUN-PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
