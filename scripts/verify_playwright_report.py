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


def case_results(data: dict, definitions: list[dict]) -> list[dict]:
    specs = []

    def visit(suite):
        specs.extend(suite.get('specs', []))
        for child in suite.get('suites', []):
            visit(child)

    for suite in data.get('suites', []):
        visit(suite)
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
    parser.add_argument('--output', type=Path, default=Path('output/playwright/agent-cases'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'outcome': 'BLOCKED', 'selected': 0, 'executed': 0, 'cases': [],
              'runner': 'Playwright Test', 'data_origin': 'generated-fixtures-only',
              'workspace_data_imported': False, 'model_mode': 'fixture', 'actual_provider_calls': 0}
    try:
        catalog = load_catalog()
        report['selected'] = len(catalog['cases'])
        report['code_revision'] = git_output('rev-parse', 'HEAD')
        report['working_tree_dirty'] = bool(git_output('status', '--porcelain'))
        report['catalog_sha256'] = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
        (args.output / 'catalog.json').write_text(json.dumps(catalog, indent=2), encoding='utf-8')
        data = json.loads((args.output / 'results.json').read_text(encoding='utf-8'))
        rows = case_results(data, catalog['cases'])
        report.update(cases=rows, passed=sum(row['status'] == 'PASS' for row in rows),
                      failures=sum(row['status'] == 'FAIL' for row in rows),
                      errors=sum(row['status'] == 'ERROR' for row in rows),
                      skipped=sum(row['status'] == 'SKIPPED' for row in rows),
                      executed=sum(row['status'] in {'PASS', 'FAIL', 'ERROR'} for row in rows),
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
    note = ('\nPlaywright HTML report: download artifact '
            f"`playwright-report-{os.getenv('GITHUB_RUN_ID', 'local')}-{os.getenv('GITHUB_RUN_ATTEMPT', '1')}` "
            'and extract it, then run `npx playwright show-report <extracted-folder>/html`. '
            'Use the Passed/Failed filters or open a case to inspect steps, errors and attachments.\n')
    with (args.output / 'summary.md').open('a', encoding='utf-8') as stream:
        stream.write(note)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a', encoding='utf-8') as stream:
            stream.write(note)
    print(f"{report['outcome']}: Playwright executed {report['executed']}/{report['selected']} cases")
    return 0 if report['outcome'] == 'RUN-PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
