"""Strict deterministic CI with real Chromium/HTTP and revision-linked evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.benchmark_context import benchmark
from testagent.browser_bridge import browser_runner_available
from testagent.context import CONTEXT_VERSION, PROMPT_VERSION


ROOT = Path(__file__).resolve().parents[1]


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []
        self.started = 0.0

    def startTest(self, test):
        self.started = time.monotonic()
        super().startTest(test)

    def record(self, test, status, detail=''):
        self.cases.append({'test_id': test.id(), 'status': status,
                           'duration_seconds': round(time.monotonic() - self.started, 6), 'detail': detail})

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, 'PASS')

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, 'FAIL', self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, 'ERROR', self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, 'SKIPPED', reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.record(test, 'EXPECTED_FAILURE', self._exc_info_to_string(err, test))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.record(test, 'UNEXPECTED_SUCCESS')

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.record(subtest, 'FAIL', self._exc_info_to_string(err, test))


def quality_gate(selected: int, result: unittest.TestResult) -> bool:
    return bool(selected > 0 and result.testsRun == selected and result.wasSuccessful()
                and not result.skipped and not result.expectedFailures)


def git_output(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, encoding='utf-8').strip()


def validate_browser_evidence(root: Path) -> dict:
    """Require matching reporter rows and actual artifact files for real runs."""
    bundles = list(root.glob('*/runs.json'))
    if not bundles:
        raise RuntimeError('Missing real browser workflow evidence bundles')
    run_count, result_count, artifact_count = 0, 0, 0
    for bundle in bundles:
        data = json.loads(bundle.read_text(encoding='utf-8'))
        cases = {case['id']: case for case in data['cases']}
        runs = {run['id']: run for run in data['runs']}
        if not runs:
            raise RuntimeError('Empty run evidence bundle')
        for run in runs.values():
            summary = json.loads(run['summary'])
            rows = [row for row in data['results'] if row['run_id'] == run['id']]
            selected = summary['test_case_ids']
            if (run['status'] not in {'COMPLETED', 'FAILED'} or not selected
                or len(rows) != len(selected) or {row['test_case_id'] for row in rows} != set(selected)):
                raise RuntimeError('Incomplete or mismatched run reporter evidence')
            run_count += 1
        for row in data['results']:
            if row['run_id'] not in runs or row['test_case_id'] not in cases:
                raise RuntimeError('Result refers to an unknown run/case')
            artifacts = json.loads(row['artifacts'])
            if cases[row['test_case_id']]['browser_case'] and (
                not any(name.endswith('.spec.ts') for name in artifacts)
                or not any(name.endswith('-trace.zip') for name in artifacts)):
                raise RuntimeError('Browser result lacks spec/trace evidence')
            for name in artifacts:
                directory = (bundle.parent / 'artifacts' / row['run_id']).resolve()
                artifact = (directory / name).resolve()
                if not artifact.is_relative_to(directory) or not artifact.is_file():
                    raise RuntimeError('Missing or out-of-scope artifact file')
                artifact_count += 1
            result_count += 1
    return {'complete': True, 'bundles': len(bundles), 'runs': run_count,
            'results': result_count, 'artifact_files': artifact_count}


def write_junit(path: Path, report: dict):
    cases = report.get('cases', [])
    suite = ET.Element('testsuite', name='TestAgent', tests=str(report.get('executed', 0)),
                       failures=str(sum(case['status'] == 'FAIL' for case in cases)),
                       errors=str(sum(case['status'] == 'ERROR' for case in cases)),
                       skipped=str(sum(case['status'] == 'SKIPPED' for case in cases)))
    for case in cases:
        node = ET.SubElement(suite, 'testcase', name=case['test_id'], time=str(case['duration_seconds']))
        if case['status'] != 'PASS':
            kind = 'skipped' if case['status'] == 'SKIPPED' else 'failure' if case['status'] == 'FAIL' else 'error'
            ET.SubElement(node, kind, message=case['status']).text = case['detail']
    ET.ElementTree(suite).write(path, encoding='utf-8', xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output/aoce/ci'))
    parser.add_argument('--pattern', default='test_*.py')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    evidence_path = args.output / 'browser' / uuid.uuid4().hex
    previous_evidence_dir = os.environ.get('TESTAGENT_EVIDENCE_DIR')
    os.environ['TESTAGENT_EVIDENCE_DIR'] = str(evidence_path.resolve())
    report = {
        'schema_version': 'aoce-ci-1', 'run_id': os.getenv('GITHUB_RUN_ID', 'local'),
        'attempt_id': os.getenv('GITHUB_RUN_ATTEMPT', '1'),
        'trigger': os.getenv('GITHUB_EVENT_NAME', 'local'),
        'started_at': datetime.now(timezone.utc).isoformat(),
        'environment': 'isolated-local-fixtures', 'synthetic_target': True,
        'model_mode': 'fixture', 'browser_and_http_execution': 'real',
        'actual_provider_calls': 0, 'usage_status': 'NOT_APPLICABLE',
        'monetary_cost': 'UNKNOWN', 'context_version': CONTEXT_VERSION, 'prompt_version': PROMPT_VERSION,
        'selected': 0, 'executed': 0, 'cases': [], 'outcome': 'BLOCKED',
        'artifacts': ['manifest.json', 'unittest.log', 'junit.xml', 'context-benchmark.json', 'browser/'],
        'browser_evidence_path': str(evidence_path.relative_to(args.output)),
        'cleanup': {'strategy': 'Per-test owned temporary directories and loopback servers; no external data writes.',
                    'status': 'NOT_STARTED'},
    }
    try:
        report['code_revision'] = git_output('rev-parse', 'HEAD')
        report['working_tree_dirty'] = bool(git_output('status', '--porcelain'))
        report['instruction_sha256'] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / 'testagent/agent_skills').glob('*.md'))}
        if not browser_runner_available():
            raise RuntimeError('Preflight: build browser_runner and install Chromium; browser checks cannot be skipped')
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=args.pattern)
        report['selected'] = suite.countTestCases()
        if report['selected'] == 0:
            report['outcome'] = 'NO-TESTS'
            raise RuntimeError('Discovery selected zero tests')
        with (args.output / 'unittest.log').open('w', encoding='utf-8') as log:
            result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=EvidenceResult).run(suite)
        report.update(executed=result.testsRun, cases=result.cases, failures=len(result.failures),
                      errors=len(result.errors), skipped=len(result.skipped),
                      outcome='RUN-PASSED' if quality_gate(report['selected'], result) else 'RUN-FAILED')
        report['cleanup']['status'] = 'FIXTURE_TEARDOWN_COMPLETED' if not result.errors else 'REVIEW_ERRORS'
        context = benchmark()
        (args.output / 'context-benchmark.json').write_text(json.dumps(context, indent=2), encoding='utf-8')
        if not context['quality_gate']:
            report['outcome'] = 'RUN-FAILED'
        report['browser_evidence'] = validate_browser_evidence(evidence_path)
    except Exception:
        if report['executed']:
            report['outcome'] = 'RUN-FAILED'
        report['error'] = traceback.format_exc()
        (args.output / 'unittest.log').touch(exist_ok=True)
    finally:
        if previous_evidence_dir is None:
            os.environ.pop('TESTAGENT_EVIDENCE_DIR', None)
        else:
            os.environ['TESTAGENT_EVIDENCE_DIR'] = previous_evidence_dir
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        report['duration_seconds'] = round(time.monotonic() - started, 3)
        write_junit(args.output / 'junit.xml', report)
        (args.output / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{report['outcome']}: selected={report['selected']}, executed={report['executed']}; {args.output / 'manifest.json'}")
        summary = os.getenv('GITHUB_STEP_SUMMARY')
        if summary:
            with Path(summary).open('a', encoding='utf-8') as stream:
                stream.write(f"TestAgent: **{report['outcome']}**, {report['executed']}/{report['selected']} tests executed. "
                             'Model responses are fixtures; HTTP/Chromium executions are real. See the evidence artifact.\n')
    return 0 if report['outcome'] == 'RUN-PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
