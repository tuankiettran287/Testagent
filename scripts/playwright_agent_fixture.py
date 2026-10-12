"""Start the real API with generated data and a scripted AI boundary for Playwright.

Fixture helper routes exist only in this disposable test process, never in the
normal application. Playwright sends real HTTP requests to the application API.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import zipfile
from unittest.mock import patch

import uvicorn
from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response

from scripts.agent_function_cases import FunctionalChecks
from scripts.ci_agent_cases import load_catalog
from testagent import api, db, planner, runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    catalog = load_catalog()
    with FunctionalChecks() as checks:
        overrides = {}

        def complete(system, user, *selection):
            payload = checks.complete(system, user, *selection)
            request = json.loads(user)
            return overrides.get((request['project']['name'], request['function']), payload)

        @api.app.get('/__fixture/state')
        def fixture_state():
            return {
                'project_id': checks.project_id, 'source_id': checks.source_id,
                'code_source_id': db.one("SELECT id FROM sources WHERE project_id=? AND kind='code'",
                                         (checks.project_id,))['id'],
                'api_case': checks.api_case, 'manual_case': checks.manual_case,
                'failed_case': checks.failed_case, 'failed_run': checks.failed_run,
                'target_url': checks.project['base_url'],
                'model_calls': len(checks.calls), 'resolution_calls': checks.manager.resolve.call_count,
                'tasks': len(db.many('SELECT id FROM tasks')),
                'runs': len(db.many('SELECT id FROM runs')),
                'cases': len(db.many('SELECT id FROM test_cases')),
                'workspace_data_imported': False,
                'catalog_ids': [case['id'] for case in catalog['cases']],
            }

        @api.app.post('/__fixture/cases')
        def fixture_case(payload: dict):
            data = {key: payload[key] for key in ('automation', 'api_request') if key in payload}
            case_id = checks.insert_case(payload['title'], payload['level'], **data)
            return {'id': case_id}

        @api.app.get('/__fixture/demo-transient-health')
        def demo_transient_health(attempt: int = 0):
            return JSONResponse(status_code=503 if attempt == 0 else 200, content={
                'status': 'starting' if attempt == 0 else 'healthy',
                'attempt': attempt, 'controlled_status_demo': True,
            })

        @api.app.post('/__fixture/parse-python')
        def parse_python(payload: dict):
            ast.parse(payload['code'])
            return {'syntax_valid': True, 'executed': False}

        @api.app.get('/__fixture/repository.zip')
        def generated_repository():
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                archive.writestr('generated_module.py', 'def generated_limit():\n    return 37\n')
            return Response(buffer.getvalue(), media_type='application/zip')

        @api.app.post('/__fixture/model-response')
        def fixture_model(payload: dict):
            overrides[(payload['project_name'], payload['function'])] = payload['response']
            return {'configured': True}

        @api.app.delete('/__fixture/model-response')
        def clear_model():
            overrides.clear()
            return {'cleared': True}

        @api.app.post('/__fixture/replay/{run_id}')
        def fixture_replay(run_id: str):
            owned = db.one('SELECT id FROM runs WHERE id=? AND project_id=?', (run_id, checks.project_id))
            if not owned:
                raise HTTPException(404, 'Fixture run not found')
            before = db.many('SELECT * FROM run_results WHERE run_id=?', (run_id,))
            with patch.object(runner, '_api_case', side_effect=AssertionError('Repeated execution')) as operation:
                runner.execute_run(run_id)
            after = db.many('SELECT * FROM run_results WHERE run_id=?', (run_id,))
            return {'execution_calls': operation.call_count, 'unchanged': before == after}

        @api.app.post('/__fixture/finalize')
        def fixture_finalize():
            # Export artifacts and remove owned data before Playwright terminates
            # its webServer process (including Windows forced termination).
            checks.__exit__(None, None, None)
            return {'cleanup': 'OWNED_FIXTURE_TEARDOWN_COMPLETED'}

        with patch.object(planner, 'complete_json', side_effect=complete):
            uvicorn.run(api.app, host='127.0.0.1', port=args.port, log_level='warning', access_log=False)


if __name__ == '__main__':
    main()
