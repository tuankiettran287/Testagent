"""Reviewed functional scenarios against a newly created TestAgent fixture.

Only the AI provider boundary is scripted. API handlers, persistence, validation,
the task controller, Chromium and HTTP execution use the application code.
"""
from __future__ import annotations

import ast
import io
import json
import zipfile
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from scripts.verify_agents import AgentChecks, require
from testagent import api, db, planner, runner
from testagent.skills import get_skill


class FunctionalChecks(AgentChecks):
    def complete(self, system, user, provider=None, model=None, effort=None):
        payload = super().complete(system, user, provider, model, effort)
        request = json.loads(user)
        if request['function'] == 'unit_test':
            # Unit generation receives code evidence, not requirement documents.
            payload['cases'][0]['source_ids'] = [
                request['evidence']['sources'][0]['source_id'], 'fabricated']
        return payload

    def __enter__(self):
        super().__enter__()
        try:
            self.api_events = []
            self.details = {}
            self.manager = Mock()
            self.manager.resolve.return_value = self.selection
            self.stack.enter_context(patch.object(api, 'provider_manager', self.manager))
            self.stack.enter_context(patch.object(api, 'settings', runner.settings))
            self.client = self.stack.enter_context(TestClient(api.app))
            require(len(self.client.get('/api/projects').json()) == 1,
                    'The functional suite must start with only its generated project')
            return self
        except BaseException:
            self.stack.close()
            raise

    def request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = response.text
        self.api_events.append({'method': method, 'path': path,
                                'status_code': response.status_code, 'response': body})
        return response

    def task(self, function, **options):
        response = self.request('POST', '/api/agent/tasks', json={
            'project_id': self.project_id, 'function': function,
            'prompt': 'Verify the generated status portal using its supplied requirements.',
            'agent_mode': 'single', **options,
        })
        require(response.status_code == 202, response.text)
        task = self.request('GET', '/api/agent/tasks/' + response.json()['id']).json()
        self.details['task_id'] = task['id']
        self.details['task_status'] = task['status']
        return task

    def run_case(self, case_id):
        response = self.request('POST', '/api/tests/execute', json={
            'project_id': self.project_id, 'test_case_ids': [case_id]})
        require(response.status_code == 202, response.text)
        return self.request('GET', '/api/runs/' + response.json()['id']).json()

    def check_function(self, function):
        skill = get_skill(function)
        options = {}
        if skill.requires == 'cases':
            options['case_ids'] = [self.api_case if function == 'run_tests' else self.manual_case]
        if skill.requires == 'run':
            options['run_id'] = self.failed_run
        before_calls = len(self.calls)
        before_resolve = self.manager.resolve.call_count
        task = self.task(function, **options)
        require(task['status'] == 'COMPLETED', f"{function}: {task['status']}: {task['error']}")
        output = json.loads(task['summary'])
        if function == 'orchestrator':
            require(task['intent'] == 'performance' and task['orchestration']['function'] == 'performance',
                    'Routing did not persist the fixture-selected specialist')
            require(len(self.calls) - before_calls == 2, 'Routing and specialist must both execute')
        else:
            require(output['skill_id'] == function, 'The wrong specialist produced the result')
        if skill.mode == 'analysis':
            require(bool(output['findings']), 'No analysis finding was persisted')
            require(all('fabricated' not in item['evidence_ids'] for item in output['findings']),
                    'Fabricated evidence must be removed')
        if skill.workflow == 'browser' or skill.mode == 'execution':
            require(output['execution']['status'] == 'COMPLETED', 'The real final run failed')
            require(output['execution']['counts']['PASS'] == 1, 'Expected exactly one executed passing case')
            actual_run = self.request('GET', '/api/runs/' + output['run_id']).json()
            require(len(actual_run['results']) == 1 and actual_run['results'][0]['status'] == 'PASS',
                    'Task counts must match the persisted result')
            if skill.workflow == 'browser':
                require(any(name.endswith('-trace.zip') for name in actual_run['results'][0]['artifacts']),
                        'The browser execution must retain a real trace')
                require(output['context_manifest']['task_id'] == task['id'], 'Context belongs to another task')
        if function == 'run_tests':
            require(len(self.calls) == before_calls and self.manager.resolve.call_count == before_resolve,
                    'Deterministic suite execution must work without resolving or calling AI')
        if function in {'automation_builder', 'repair_automation'}:
            original_id = self.manual_case if function == 'automation_builder' else self.failed_case
            require(output['case_ids'] == [original_id], 'Building/repair must preserve case identity')
            updated = self.request('GET', '/api/tests/' + original_id).json()
            require(updated['expected'] == ['Status text contains Healthy'], 'The original oracle changed')
            require(any(action['action'] == 'assert_text' and action.get('value') == 'Healthy'
                        for action in updated['automation']['actions']), 'The outcome assertion was removed')
        if function in {'gen_testcase', 'api_test', 'unit_test'}:
            require(output['case_count'] == 1, 'Expected one persisted generated case')
            generated = self.request('GET', '/api/tests/' + output['case_ids'][0]).json()
            expected_source = (db.one("SELECT id FROM sources WHERE project_id=? AND kind='code'",
                                      (self.project_id,))['id'] if function == 'unit_test' else self.source_id)
            require(generated['source_ids'] == [expected_source], 'Generated case lost source grounding')
            if function == 'gen_testcase':
                require(generated['readiness']['status'] == 'manual', 'A manual draft must not be marked runnable')
            elif function == 'api_test':
                run = self.run_case(generated['id'])
                require(run['status'] == 'COMPLETED' and run['results'][0]['status'] == 'PASS',
                        'Generated API case failed against the real HTTP fixture')
            else:
                ast.parse(generated['unit_test_code'])
                self.details['unit_code_validation'] = 'syntax checked; proposal not executed'
        if function == 'report':
            response = self.request('GET', f"/api/agent/tasks/{task['id']}/report")
            require(response.status_code == 200 and self.failed_run in response.text,
                    'The downloadable report must refer to the selected real run')

    def manual_rejected(self):
        manual = self.insert_case('Generated manual-only case', 'ui')
        before = len(db.many('SELECT id FROM runs'))
        response = self.request('POST', '/api/tests/execute', json={
            'project_id': self.project_id, 'test_case_ids': [manual]})
        require(response.status_code == 422, 'Manual case was admitted for execution')
        require(len(db.many('SELECT id FROM runs')) == before, 'Rejected case created a run')

    def cross_origin_rejected(self):
        case_id = self.insert_case('Generated foreign-origin request', 'api', api_request={
            'method': 'GET', 'path': 'https://outside.invalid/health', 'expected_status': 200})
        before = len(db.many('SELECT id FROM runs'))
        response = self.request('POST', '/api/tests/execute', json={
            'project_id': self.project_id, 'test_case_ids': [case_id]})
        require(response.status_code == 422, 'Cross-origin case was admitted')
        require(len(db.many('SELECT id FROM runs')) == before, 'Cross-origin rejection created a run')

    def foreign_case_rejected(self):
        other = self.request('POST', '/api/projects', json={'name': 'Generated other project'}).json()['id']
        before = len(db.many('SELECT id FROM tasks'))
        calls = len(self.calls)
        response = self.request('POST', '/api/agent/tasks', json={
            'project_id': other, 'function': 'case_review', 'prompt': 'Review the selected test case.',
            'case_ids': [self.api_case]})
        require(response.status_code == 422, 'A foreign project case was accepted')
        require(len(db.many('SELECT id FROM tasks')) == before and len(self.calls) == calls,
                'Foreign case rejection must precede task creation and AI dispatch')

    def assertion_failure_reported(self):
        case_id = self.insert_case('Generated deliberately wrong HTTP oracle', 'api', api_request={
            'method': 'GET', 'path': '/health', 'expected_status': 201})
        run = self.run_case(case_id)
        require(run['status'] == 'FAILED' and run['results'][0]['status'] == 'FAIL',
                'An actual HTTP 200 versus expected 201 must be reported as FAIL')
        require(run['summary']['counts']['PASS'] == 0 and run['summary']['counts']['FAIL'] == 1,
                'Failed assertions must not contribute a pass')
        self.details['expected_product_run_status'] = 'FAILED'
        self.details['run_id'] = run['id']

    def duplicate_delivery(self):
        run = self.run_case(self.api_case)
        before = db.many('SELECT * FROM run_results WHERE run_id=?', (run['id'],))
        with patch.object(runner, '_api_case', side_effect=AssertionError('Duplicate execution')):
            runner.execute_run(run['id'])
        require(db.many('SELECT * FROM run_results WHERE run_id=?', (run['id'],)) == before,
                'A repeated delivery changed the completed results')

    def invalid_model_rejected(self):
        before = len(db.many('SELECT id FROM test_cases'))
        payload = {'intent': 'test_generation', 'summary': 'Invalid scripted response.',
                   'cases': [], 'shell_command': 'unsupported-command'}
        with patch.object(planner, 'complete_json', return_value=payload):
            task = self.task('gen_testcase')
        require(task['status'] == 'FAILED' and task['error'], 'Invalid model output was accepted')
        require(len(db.many('SELECT id FROM test_cases')) == before, 'Invalid response persisted a case')

    def generate_without_execution(self):
        before = len(db.many('SELECT id FROM runs'))
        task = self.task('ui_automation', execution_mode='generate')
        require(task['status'] == 'READY', task['error'])
        output = json.loads(task['summary'])
        require(output['execution'] is None and len(output['executable_ids']) == 1,
                'Generate-only output is not a ready draft')
        require(len(db.many('SELECT id FROM runs')) == before, 'Generate-only mode executed a final run')

    def missing_context(self):
        project = self.request('POST', '/api/projects', json={'name': 'Generated empty project'}).json()['id']
        calls = len(self.calls)
        with patch.object(planner, 'complete_json', return_value={
            'function': 'repo_under', 'reason': 'Repository architecture analysis needs source code.'}) as model:
            task = self.task('orchestrator', project_id=project)
        require(task['status'] == 'NEEDS_INPUT', 'Missing code must request input')
        require(model.call_count == 1 and len(self.calls) == calls,
                'Missing evidence must stop before specialist dispatch')
        require(bool(json.loads(task['summary'])['blocked_reason']), 'No reason was provided for the block')

    def document_ingestion(self):
        content = 'Generated acceptance requirement: invoice limit is exactly 37 items.'
        response = self.request('POST', f'/api/projects/{self.project_id}/documents', files={
            'file': ('generated-requirement.txt', content.encode(), 'text/plain')})
        require(response.status_code == 201, response.text)
        source_id = response.json()['source_id']
        hits = self.request('GET', f'/api/projects/{self.project_id}/knowledge', params={'q': 'invoice'}).json()
        require(any(item['source_id'] == source_id and '37 items' in item['content'] for item in hits),
                'Uploaded generated requirement could not be retrieved')

    def repository_ingestion(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as bundle:
            bundle.writestr('generated_module.py', 'def generated_limit():\n    return 37\n')
        response = self.request('POST', f'/api/projects/{self.project_id}/repositories/zip', files={
            'file': ('generated-repository.zip', archive.getvalue(), 'application/zip')})
        require(response.status_code == 201 and response.json()['imported'] == 1, response.text)
        source = db.one('SELECT kind,content FROM sources WHERE id=?', (response.json()['source_ids'][0],))
        require(source['kind'] == 'code' and 'generated_limit' in source['content'], 'ZIP source was not indexed')

    def openapi_ingestion(self):
        document = {'openapi': '3.0.3', 'info': {'title': 'Generated API', 'version': '1.0'},
                    'paths': {'/health': {'get': {'responses': {'200': {'description': 'Healthy'}}}}}}
        response = self.request('POST', f'/api/projects/{self.project_id}/openapi', files={
            'file': ('generated-openapi.json', json.dumps(document).encode(), 'application/json')})
        require(response.status_code == 201, response.text)
        source = db.one('SELECT kind,content FROM sources WHERE id=?', (response.json()['source_id'],))
        require(source['kind'] == 'openapi' and '/health' in source['content'] and '200' in source['content'],
                'The generated OpenAPI contract was not indexed')


SCENARIOS = {name: getattr(FunctionalChecks, name) for name in (
    'manual_rejected', 'cross_origin_rejected', 'foreign_case_rejected',
    'assertion_failure_reported', 'duplicate_delivery', 'invalid_model_rejected',
    'generate_without_execution', 'missing_context', 'document_ingestion',
    'repository_ingestion', 'openapi_ingestion',
)}
