import json
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from testagent import api as api_module, db, planner, runner
from testagent.config import settings
from testagent.readiness import case_readiness


class SuiteExecutionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        config = replace(settings, data_dir=Path(self.directory.name))
        self.manager = Mock()
        self.manager.resolve.side_effect = ValueError('AI disconnected')
        self.patches = [patch.object(db, 'settings', config), patch.object(runner, 'settings', config),
                        patch.object(api_module, 'provider_manager', self.manager)]
        for item in self.patches:
            item.start()
        self.client = TestClient(api_module.app)
        self.client.__enter__()
        self.project = self.client.post('/api/projects', json={'name': 'Suite fixture', 'base_url': 'http://localhost:9000', 'environment': 'local'}).json()['id']
        self.ids = [self.insert_case(f'Case {index}') for index in range(5)]

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def insert_case(self, title, project=None, executable=True):
        case_id = db.uid()
        db.execute('''INSERT INTO test_cases (id, project_id, title, level, type, priority, preconditions,
                      steps, expected, source_ids, api_request, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                   (case_id, project or self.project, title, 'api', 'positive', 'medium', '[]', '["Request endpoint"]',
                    '["Returns 200"]', '[]', json.dumps({'method': 'GET', 'path': '/health', 'expected_status': 200}) if executable else None, db.now()))
        return case_id

    def test_parallel_execution_is_bounded_and_reports_completed_cases_during_run(self):
        lock = threading.Lock()
        active, maximum = 0, 0
        seen_completed = []
        def response(case, base_url):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(active, maximum)
            seen_completed.append(json.loads(db.one('SELECT summary FROM runs')['summary'])['completed'])
            time.sleep(0.05)
            with lock:
                active -= 1
            return ('FAIL' if case['id'] == self.ids[1] else 'PASS'), 'Fixture assertion', []
        with patch.object(runner, '_api_case', side_effect=response):
            run_id = runner.prepare_run(self.project, self.ids, 'parallel', 2)
            runner.execute_run(run_id)
        run = self.client.get('/api/runs/' + run_id).json()
        self.assertEqual(maximum, 2)
        self.assertGreater(max(seen_completed), 0)
        self.assertEqual(run['status'], 'FAILED')
        self.assertEqual(run['summary']['completed'], 5)
        self.assertEqual(run['summary']['workers'], 2)
        self.assertEqual(run['summary']['test_case_ids'], self.ids)
        self.assertEqual(run['summary']['counts']['PASS'], 4)
        self.assertEqual(len(run['results']), 5)
        tests = self.client.get(f'/api/projects/{self.project}/tests').json()
        self.assertTrue(all(case['last_run_id'] == run_id for case in tests))

    def test_sequential_execution_keeps_requested_order_and_continues_after_error(self):
        order = []
        def response(case, base_url):
            order.append(case['id'])
            if len(order) == 1:
                raise ValueError('Fixture transport failure')
            return 'PASS', 'Passed', []
        requested = [self.ids[3], self.ids[1], self.ids[4]]
        with patch.object(runner, '_api_case', side_effect=response):
            run_id = runner.prepare_run(self.project, requested, 'sequential', 4)
            runner.execute_run(run_id)
        self.assertEqual(order, requested)
        run = self.client.get('/api/runs/' + run_id).json()
        self.assertEqual(run['summary']['counts']['ERROR'], 1)
        self.assertEqual(run['summary']['counts']['PASS'], 2)
        self.assertEqual(run['summary']['workers'], 1)

    def test_execution_agent_runs_selected_cases_without_ai_account_or_model_call(self):
        with patch.object(planner, 'complete_json') as model, patch.object(runner, '_api_case', return_value=('PASS', 'Passed', [])):
            response = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'function': 'run_tests', 'prompt': 'Run selected cases.', 'case_ids': self.ids[:2], 'run_mode': 'parallel', 'workers': 2})
        self.assertEqual(response.status_code, 202, response.text)
        task = self.client.get('/api/agent/tasks/' + response.json()['id']).json()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertIsNone(task['ai_provider'])
        self.assertEqual(json.loads(task['summary'])['execution']['counts']['PASS'], 2)
        self.manager.resolve.assert_not_called()
        model.assert_not_called()

    def test_review_gets_selected_cases_and_filters_fabricated_evidence_ids(self):
        self.manager.resolve.side_effect = None
        self.manager.resolve.return_value = {'provider': 'codex', 'model': 'native', 'effort': 'high'}
        payload = {'summary': 'Selected cases need stronger response assertions.', 'findings': [{'title': 'Weak response coverage', 'detail': 'Only HTTP status is checked.', 'evidence_ids': [self.ids[0], 'invented']}], 'recommendations': ['Add body assertions after confirming the contract.']}
        with patch.object(planner, '_website_context', return_value=None), patch.object(planner, 'complete_json', return_value=payload) as model:
            response = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'function': 'case_review', 'prompt': 'Review selected test cases.', 'case_ids': self.ids[:1]})
        task = self.client.get('/api/agent/tasks/' + response.json()['id']).json()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        request = json.loads(model.call_args.args[1])
        self.assertEqual([case['id'] for case in request['evidence']['test_cases']], self.ids[:1])
        self.assertEqual(json.loads(task['summary'])['findings'][0]['evidence_ids'], self.ids[:1])

    def test_foreign_case_and_manual_case_are_rejected_without_creating_runs(self):
        other = self.client.post('/api/projects', json={'name': 'Other project'}).json()['id']
        foreign = self.insert_case('Foreign case', project=other)
        manual = self.insert_case('Manual case', executable=False)
        for case_id in [foreign, manual]:
            response = self.client.post('/api/tests/execute', json={'project_id': self.project, 'test_case_ids': [case_id]})
            self.assertEqual(response.status_code, 422, response.text)
        response = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'function': 'automation_builder', 'prompt': 'Build browser automation.', 'case_ids': [foreign]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(db.many('SELECT * FROM runs'), [])

    def test_setup_error_terminates_run_instead_of_leaving_it_queued(self):
        run_id = runner.prepare_run(self.project, self.ids[:1])
        with patch.object(runner, '_execute_run', side_effect=OSError('Artifact directory unavailable')):
            runner.execute_run(run_id)
        run = self.client.get('/api/runs/' + run_id).json()
        self.assertEqual(run['status'], 'FAILED')
        self.assertIn('directory unavailable', run['summary']['error'])

    def test_repeated_delivery_does_not_execute_a_finished_run_again(self):
        run_id = runner.prepare_run(self.project, self.ids[:1])
        with patch.object(runner, '_api_case', return_value=('PASS', 'Passed', [])) as request:
            runner.execute_run(run_id)
            runner.execute_run(run_id)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(db.many('SELECT * FROM run_results WHERE run_id=?', (run_id,))), 1)

    def test_concurrent_delivery_claims_the_run_only_once(self):
        run_id = runner.prepare_run(self.project, self.ids[:1])
        entered, release = threading.Event(), threading.Event()
        def response(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test worker was not released')
            return 'PASS', 'Passed', []
        with patch.object(runner, '_api_case', side_effect=response) as request:
            worker = threading.Thread(target=runner.execute_run, args=(run_id,))
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                # A second delivery must return without waiting for the first case.
                runner.execute_run(run_id)
            finally:
                release.set()
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(request.call_count, 1)
        self.assertEqual(db.one('SELECT status FROM runs WHERE id=?', (run_id,))['status'], 'COMPLETED')

    def test_queued_run_rechecks_production_policy_before_network_access(self):
        run_id = runner.prepare_run(self.project, self.ids[:1])
        db.execute("UPDATE projects SET environment='production' WHERE id=?", (self.project,))
        with patch.object(runner, '_api_case') as request:
            runner.execute_run(run_id)
        request.assert_not_called()
        run = self.client.get('/api/runs/' + run_id).json()
        self.assertEqual(run['status'], 'FAILED')
        self.assertIn('production', run['summary']['error'])

    def test_queued_run_rechecks_changed_case_before_executing_any_case(self):
        run_id = runner.prepare_run(self.project, self.ids[:2])
        db.execute('UPDATE test_cases SET api_request=NULL WHERE id=?', (self.ids[1],))
        with patch.object(runner, '_api_case') as request:
            runner.execute_run(run_id)
        request.assert_not_called()
        self.assertEqual(db.one('SELECT status FROM runs WHERE id=?', (run_id,))['status'], 'FAILED')

    def test_corrupt_run_summary_is_reported_as_a_terminal_failure(self):
        run_id = runner.prepare_run(self.project, self.ids[:1])
        db.execute('UPDATE runs SET summary=? WHERE id=?', ('invalid json', run_id))
        runner.execute_run(run_id)
        run = self.client.get('/api/runs/' + run_id).json()
        self.assertEqual(run['status'], 'FAILED')
        self.assertIn('error', run['summary'])

    def test_invalid_queued_execution_options_fail_before_network_access(self):
        for patch_summary in ({'test_case_ids': []}, {'mode': 'unsupported'}, {'workers': 99}):
            with self.subTest(summary=patch_summary):
                run_id = runner.prepare_run(self.project, self.ids[:1])
                summary = json.loads(db.one('SELECT summary FROM runs WHERE id=?', (run_id,))['summary'])
                summary.update(patch_summary)
                db.execute('UPDATE runs SET summary=? WHERE id=?', (json.dumps(summary), run_id))
                with patch.object(runner, '_api_case') as request:
                    runner.execute_run(run_id)
                request.assert_not_called()
                self.assertEqual(db.one('SELECT status FROM runs WHERE id=?', (run_id,))['status'], 'FAILED')


class CaseReadinessTests(unittest.TestCase):
    def test_browser_case_must_start_with_navigation_and_assert_expected_outcome(self):
        case = {'automation': {'actions': [{'action': 'navigate', 'url': '/'}]}}
        self.assertEqual(case_readiness(case, 'http://localhost')['status'], 'needs_input')
        case['automation']['actions'].append({'action': 'assert_visible', 'target': {'role': 'heading', 'name': 'Home'}})
        self.assertEqual(case_readiness(case, 'http://localhost')['status'], 'ready')
        self.assertEqual(case_readiness(case, '')['status'], 'needs_input')
        case['automation']['actions'].pop(0)
        self.assertEqual(case_readiness(case, 'http://localhost')['status'], 'needs_input')

    def test_cross_origin_and_manual_cases_are_not_runnable(self):
        case = {'api_request': {'method': 'GET', 'path': 'https://other.example/health', 'expected_status': 200}}
        self.assertEqual(case_readiness(case, 'http://localhost')['status'], 'invalid')
        self.assertEqual(case_readiness({}, 'http://localhost')['status'], 'manual')


if __name__ == '__main__':
    unittest.main()
