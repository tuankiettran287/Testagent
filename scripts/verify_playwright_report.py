"""Check native Playwright outcomes and publish a per-case GitHub summary."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import traceback
from pathlib import Path

from scripts.ci_agent_cases import CATALOG, load_catalog, write_summary
from scripts.ci_verify import git_output, validate_browser_evidence


def native_specs(data: dict) -> list[dict]:
    specs = []
    def visit(suite):
        specs.extend(suite.get('specs', []))
        for child in suite.get('suites', []):
            visit(child)
    for suite in data.get('suites', []):
        visit(suite)
    return specs


def select_cases(catalog: dict, suite: str) -> list[dict]:
    if suite not in {'functional', 'status-demo'}:
        raise ValueError(f'Unknown agent test suite: {suite}')
    return [case for case in catalog['cases'] if bool(case.get('report_demo')) == (suite == 'status-demo')]


def suite_results(data: dict, definitions: list[dict], suite: str) -> list[dict]:
    specs = native_specs(data)
    known = {case['id'] for case in definitions}
    if any(spec['title'].split(' ', 1)[0] not in known for spec in specs):
        raise ValueError('Unexpected case outside the selected suite')
    if suite == 'functional':
        return case_results(data, definitions)
    return demo_results(specs, definitions)


def demo_results(specs: list[dict], definitions: list[dict]) -> list[dict]:
    known = {case['id']: case for case in definitions}
    found = {}
    for spec in specs:
        case_id = spec['title'].split(' ', 1)[0]
        if case_id not in known or case_id in found or len(spec.get('tests', [])) != 1:
            raise ValueError('Unknown, duplicate or multi-project report demo case')
        case = spec['tests'][0]
        results = case.get('results', [])
        attempts = [result['status'] for result in results]
        status = {'expected': 'PASS', 'unexpected': 'FAIL', 'flaky': 'FLAKY', 'skipped': 'SKIPPED'}.get(case['status'], 'ERROR')
        if case.get('expectedStatus') != ('skipped' if status == 'SKIPPED' else 'passed'):
            status = 'ERROR'
        definition = known[case_id]
        found[case_id] = {
            'status': status, 'attempts': attempts,
            'matches_expected_demo': status == definition['expected_report_status'] and attempts == definition['expected_attempts'],
            'duration_seconds': round(sum(result.get('duration', 0) for result in results) / 1000, 3),
            'detail': '\n'.join(error.get('message', str(error)) for result in results for error in result.get('errors', [])),
        }
    return [{**case, 'test_id': case['id'], **found.get(case['id'], {
        'status': 'NOT_RUN', 'attempts': [], 'matches_expected_demo': False,
        'duration_seconds': 0, 'detail': 'Not executed by Playwright'})} for case in definitions]


def case_results(data: dict, definitions: list[dict]) -> list[dict]:
    specs = native_specs(data)
    known = {item['id'] for item in definitions}
    found = {}
    for spec in specs:
        match = re.match(r'^(AGENT-[FNI]\d{2})\s', spec['title'])
        case_id = match.group(1) if match else None
        if case_id not in known or case_id in found:
            raise ValueError('Unexpected or duplicate Playwright case ID')
        tests = spec.get('tests', [])
        results = tests[0].get('results', []) if len(tests) == 1 else []
        if len(tests) != 1 or len(results) > 1:
            raise ValueError('Each reviewed case must execute once with no retry')
        result = results[0] if results else {}
        status = result.get('status', 'not_run')
        if tests[0].get('expectedStatus') != 'passed':
            status = 'invalid_expected_status'
        found[case_id] = {
            'status': {'passed': 'PASS', 'failed': 'FAIL', 'timedOut': 'ERROR',
                       'skipped': 'SKIPPED', 'interrupted': 'ERROR', 'not_run': 'NOT_RUN'}.get(status, 'ERROR'),
            'duration_seconds': round(result.get('duration', 0) / 1000, 3),
            'detail': '\n'.join(error.get('message', str(error)) for error in result.get('errors', [])),
        }
    return [{**definition, 'test_id': definition['id'],
             **found.get(definition['id'], {'status': 'NOT_RUN', 'duration_seconds': 0, 'detail': 'Not executed by Playwright'})}
            for definition in definitions]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('functional', 'status-demo'), default='functional')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    args.output = args.output or Path('output/playwright') / ('agent-cases' if args.suite == 'functional' else 'status-demo')
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'outcome': 'BLOCKED', 'selected': 0, 'executed': 0, 'cases': [],
              'suite': args.suite, 'run_id': os.getenv('GITHUB_RUN_ID', 'local'),
              'attempt_id': os.getenv('GITHUB_RUN_ATTEMPT', '1'),
              'runner': 'Playwright Test', 'data_origin': 'generated-fixtures-only',
              'workspace_data_imported': False, 'model_mode': 'fixture', 'actual_provider_calls': 0}
    try:
        catalog = load_catalog()
        definitions = select_cases(catalog, args.suite)
        report['selected'] = len(definitions)
        report['selected_case_ids'] = [case['id'] for case in definitions]
        report['code_revision'] = git_output('rev-parse', 'HEAD')
        report['working_tree_dirty'] = bool(git_output('status', '--porcelain'))
        report['catalog_sha256'] = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
        (args.output / 'catalog.json').write_text(json.dumps({**catalog, 'suite': args.suite, 'cases': definitions}, indent=2), encoding='utf-8')
        data = json.loads((args.output / 'results.json').read_text(encoding='utf-8'))
        rows = suite_results(data, definitions, args.suite)
        suite_matched = bool(rows) and all(
            row['status'] == 'PASS' if args.suite == 'functional' else row['matches_expected_demo'] for row in rows)
        report.update(cases=rows, passed=sum(row['status'] == 'PASS' for row in rows),
                      failures=sum(row['status'] == 'FAIL' for row in rows),
                      flaky=sum(row['status'] == 'FLAKY' for row in rows),
                      errors=sum(row['status'] == 'ERROR' for row in rows),
                      skipped=sum(row['status'] == 'SKIPPED' for row in rows),
                      executed=sum(row['status'] in {'PASS', 'FAIL', 'FLAKY', 'ERROR'} for row in rows),
                      functional_outcome=('RUN-PASSED' if suite_matched else 'RUN-FAILED') if args.suite == 'functional' else 'NOT_SELECTED',
                      demo_outcomes_match=suite_matched if args.suite == 'status-demo' else None,
                      validation='MATCHED' if suite_matched and not data.get('errors') else 'NOT_MATCHED',
                      playwright_stats=data.get('stats', {}), global_errors=data.get('errors', []))
        report['outcome'] = 'RUN-PASSED' if all(row['status'] == 'PASS' for row in rows) and not data.get('errors') else 'RUN-FAILED'
        cleanup = json.loads((args.output / 'fixture-finalization.json').read_text(encoding='utf-8'))
        if cleanup['cleanup'] != 'OWNED_FIXTURE_TEARDOWN_COMPLETED':
            raise ValueError('Fixture cleanup did not complete')
        report['cleanup'] = cleanup['cleanup']
        report['browser_evidence'] = validate_browser_evidence(args.output / 'browser')
        for path in ('html/index.html', 'junit.xml'):
            if not (args.output / path).is_file():
                raise ValueError(f'Missing Playwright report file: {path}')
    except Exception:
        report['outcome'] = 'RUN-FAILED' if report['executed'] else 'BLOCKED'
        report['error'] = traceback.format_exc()
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    write_summary(args.output / 'summary.md', report)
    scope_note = ('This job selects only the 30 functional cases. Every case must PASS without retries or skips.'
                  if args.suite == 'functional' else
                  'This job selects only the 7 report-status demos. The two deliberately incorrect assertions keep this job red. '
                  'Only the two controlled flaky demos allow one retry; SKIP is not PASS.')
    note = (f'\n{scope_note}\n'
            '\nPlaywright HTML report: download artifact '
            f"`playwright-{args.suite}-report-{report['run_id']}-{report['attempt_id']}` "
            'and extract it, then run `npx playwright show-report <extracted-folder>/html`. '
            'Use the Passed/Failed filters or open a case to inspect steps, errors and attachments.\n')
    with (args.output / 'summary.md').open('a', encoding='utf-8') as stream:
        stream.write(note)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a', encoding='utf-8') as stream:
            stream.write(note)
    print(f"{report['outcome']}: Playwright executed {report['executed']}/{report['selected']} cases")
    # Verify reporting against the explicitly requested demos without changing
    # their actual FAIL/FLAKY/SKIP results or the failed Playwright step exit code.
    return 0 if report.get('validation') == 'MATCHED' and not report.get('error') else 1


if __name__ == '__main__':
    raise SystemExit(main())
