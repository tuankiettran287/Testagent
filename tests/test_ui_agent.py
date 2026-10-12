import json
import tempfile
import threading
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from testagent import api as api_module, db, planner, ui_agent
from testagent.browser_bridge import BrowserSession, invoke_browser
from testagent.config import settings


class UiWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = replace(settings, data_dir=Path(self.directory.name))
        manager = Mock()
        manager.resolve.return_value = {'provider': 'codex', 'model': 'native', 'effort': 'high'}
        self.login_actions = [
            {'action': 'fill', 'target': {'placeholder': 'Username'}, 'value': 'demo'},
            {'action': 'fill', 'target': {'placeholder': 'Password'}, 'value': 'test-secret'},
            {'action': 'click', 'target': {'testid': 'submit', 'test_attribute': 'data-test'}},
        ]
        self.start = {'url': 'http://localhost:9000/login', 'title': 'Login', 'text': 'Demo account: demo / test-secret', 'elements': []}
        self.destination = {'url': 'http://localhost:9000/dashboard', 'title': 'Dashboard', 'text': 'Welcome demo',
                            'elements': [{'testid': 'welcome', 'test_attribute': 'data-test', 'text': 'Welcome demo'}]}
        self.session = Mock()
        self.session.initial = {'snapshot': self.start}
        self.session.__enter__ = Mock(return_value=self.session)
        self.session.__exit__ = Mock(return_value=False)
        self.session.request.return_value = {'snapshot': self.destination, 'performed': self.login_actions}
        self.plan = {'intent': 'ui_automation', 'summary': 'Test the real login journey.', 'cases': [{
            'title': 'Log in with demo account', 'level': 'e2e', 'type': 'positive', 'priority': 'high',
            'steps': ['Open login', 'Submit demo credentials', 'Check dashboard'], 'expected': ['Welcome demo is visible'],
            'automation': {'actions': [{'action': 'navigate', 'url': '/login'}, *self.login_actions,
                                     {'action': 'assert_url', 'url': '/dashboard'},
                                     {'action': 'assert_text', 'target': {'testid': 'welcome', 'test_attribute': 'data-test'}, 'value': 'Welcome demo'}]},
        }]}
        self.responses = [
            {'summary': 'Sign in with the supplied demo account.', 'scenarios': ['Successful login'], 'actions': self.login_actions},
            {'summary': 'Dashboard and Welcome demo were observed.', 'actions': [], 'done': True},
            self.plan,
        ]
        self.requests, self.phases, self.instructions = [], [], []
        self.run_passes = True
        self.patches = [patch.object(db, 'settings', self.config), patch.object(api_module, 'provider_manager', manager),
                        patch.object(api_module, 'browser_runner_available', return_value=True),
                        patch.object(ui_agent, 'BrowserSession', return_value=self.session),
                        patch.object(planner, 'complete_json', side_effect=self.generate),
                        patch.object(planner, 'execute_run', side_effect=self.execute)]
        for item in self.patches:
            item.start()
        self.client = TestClient(api_module.app)
        self.client.__enter__()
        self.project = self.client.post('/api/projects', json={'name': 'Live workflow', 'base_url': self.start['url'], 'environment': 'local'}).json()['id']

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def generate(self, system, request, provider, model, effort):
        self.instructions.append(system)
        self.requests.append(json.loads(request))
        self.phases.append(db.one('SELECT status FROM tasks')['status'])
        self.assertEqual((provider, model, effort), ('codex', 'native', 'high'))
        return self.responses.pop(0)

    def execute(self, run_id):
        self.assertEqual(db.one('SELECT status FROM tasks')['status'], 'RUNNING')
        run = db.one('SELECT * FROM runs WHERE id=?', (run_id,))
        case_ids = json.loads(run['summary'])['test_case_ids']
        self.assertEqual(len(case_ids), 1)
        case = db.decode_case(db.one('SELECT * FROM test_cases WHERE id=?', (case_ids[0],)))
        self.assertTrue(any(action['action'] == 'click' for action in case['automation']['actions']))
        counts = {'PASS': 1 if self.run_passes else 0, 'FAIL': 0 if self.run_passes else 1, 'ERROR': 0, 'TIMEOUT': 0}
        with db.connection() as connection:
            connection.execute('UPDATE runs SET status=?, summary=? WHERE id=?',
                               ('COMPLETED' if self.run_passes else 'FAILED', json.dumps({'total': 1, 'counts': counts}), run_id))

    def submit(self, **options):
        result = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'function': 'ui_automation', 'prompt': 'Log in to the website and verify the dashboard.', **options})
        self.assertEqual(result.status_code, 202, result.text)
        return self.client.get('/api/agent/tasks/' + result.json()['id']).json()

    def test_generate_mode_stores_ready_cases_without_creating_a_final_run(self):
        task = self.submit(execution_mode='generate')
        self.assertEqual(task['status'], 'READY', task['error'])
        output = json.loads(task['summary'])
        self.assertEqual(output['phase'], 'READY')
        self.assertIsNone(output['execution'])
        self.assertEqual(len(output['executable_ids']), 1)
        self.assertEqual(db.many('SELECT * FROM runs'), [])
        self.assertEqual(self.client.get(f'/api/projects/{self.project}/tests').json()[0]['readiness']['status'], 'ready')

    def test_builder_updates_original_case_and_preserves_its_expected_behavior(self):
        task = self.submit(execution_mode='generate')
        case_id = json.loads(task['summary'])['case_ids'][0]
        with db.connection() as connection:
            connection.execute('UPDATE test_cases SET automation=NULL WHERE id=?', (case_id,))
        self.plan['cases'][0]['origin_case_id'] = case_id
        self.plan['cases'][0]['title'] = 'A model should not overwrite the original title'
        self.plan['cases'][0]['expected'] = ['A model should not overwrite the original expectations']
        self.responses = [{'summary': 'The original expected dashboard was observed.', 'done': True}, self.plan]
        converted = self.submit(function='automation_builder', case_ids=[case_id], execution_mode='generate')
        self.assertEqual(converted['status'], 'READY', converted['error'])
        cases = self.client.get(f'/api/projects/{self.project}/tests').json()
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['id'], case_id)
        self.assertEqual(cases[0]['title'], 'Log in with demo account')
        self.assertEqual(cases[0]['expected'], ['Welcome demo is visible'])
        self.assertTrue(cases[0]['automation'])
        self.assertEqual(self.requests[-1]['evidence']['test_cases'][0]['id'], case_id)

    def test_builder_rejects_a_model_origin_id_outside_the_selected_cases(self):
        task = self.submit(execution_mode='generate')
        case_id = json.loads(task['summary'])['case_ids'][0]
        original = self.client.get(f'/api/tests/{case_id}').json()
        self.plan['cases'][0]['origin_case_id'] = 'unselected-case'
        self.responses = [{'summary': 'The original dashboard was observed.', 'done': True}, self.plan]
        converted = self.submit(function='automation_builder', case_ids=[case_id], execution_mode='generate')
        self.assertEqual(converted['status'], 'FAILED')
        self.assertIn('origin_case_id', converted['error'])
        self.assertEqual(json.loads(converted['summary'])['phase'], 'FAILED')
        self.assertEqual(self.client.get(f'/api/tests/{case_id}').json(), original)

    def test_repair_cannot_remove_an_original_outcome_assertion(self):
        self.run_passes = False
        task = self.submit()
        run_id = json.loads(task['summary'])['run_id']
        case_id = json.loads(task['summary'])['case_ids'][0]
        db.execute('INSERT INTO run_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (db.uid(), run_id, case_id, 'FAIL', 100, 'ASSERTION', 'Wrong dashboard title', '[]'))
        self.plan['cases'][0]['origin_case_id'] = case_id
        self.plan['cases'][0]['automation']['actions'] = [action for action in self.plan['cases'][0]['automation']['actions'] if action['action'] != 'assert_text']
        self.responses = [{'summary': 'Inspecting a failed assertion.', 'done': True}, self.plan]
        repaired = self.submit(function='repair_automation', run_id=run_id, execution_mode='generate')
        self.assertEqual(repaired['status'], 'FAILED')
        self.assertIn('retain every original', repaired['error'])
        original = self.client.get(f'/api/tests/{case_id}').json()
        self.assertTrue(any(action['action'] == 'assert_text' for action in original['automation']['actions']))

    def test_login_is_observed_then_planned_and_run_with_pinned_effort(self):
        task = self.submit()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        summary = json.loads(task['summary'])
        self.assertEqual(summary['execution']['counts']['PASS'], 1)
        self.assertEqual(summary['manual_count'], 0)
        self.assertTrue(summary['run_id'])
        self.assertIn('locator-mastery.md', summary['skills'])
        self.assertEqual(self.phases, ['PLANNING', 'EXPLORING', 'GENERATING'])
        self.assertEqual(self.requests[1]['observation']['url'], self.destination['url'])
        self.assertEqual(self.requests[1]['performed_actions'][1:], self.login_actions)
        self.assertEqual(self.requests[2]['evidence']['browser_journey']['observations'][-1]['url'], self.destination['url'])
        self.session.__exit__.assert_called_once()
        self.assertEqual(db.many('SELECT * FROM sources'), [])

    def test_live_decisions_and_final_generation_load_their_actual_instruction_files(self):
        task = self.submit(execution_mode='generate')
        self.assertEqual(task['status'], 'READY', task['error'])
        for instructions in self.instructions:
            self.assertIn('instruction file: automation-core.md', instructions)
            self.assertIn('instruction file: ui-automation.md', instructions)
            self.assertIn('instruction file: locator-mastery.md', instructions)
        for decision_prompt in self.instructions[:-1]:
            self.assertIn('Active phase: exploration. Return BrowserDecision only', decision_prompt)
            self.assertNotIn('instruction file: automation-patterns.md', decision_prompt)
            self.assertNotIn('example_account', decision_prompt)
        self.assertIn('Active phase: final. Return GeneratedPlan only', self.instructions[-1])
        self.assertIn('instruction file: automation-patterns.md', self.instructions[-1])
        self.assertEqual(json.loads(task['summary'])['skills'],
                         ['automation-core.md', 'ui-automation.md', 'locator-mastery.md', 'automation-patterns.md'])

    def test_missing_credentials_need_input_instead_of_fake_completion(self):
        self.responses = [{'summary': 'Login credentials are not supplied.', 'scenarios': ['Login'], 'blocked_reason': 'Provide a test username and password.'}]
        task = self.submit()
        self.assertEqual(task['status'], 'NEEDS_INPUT')
        self.assertIn('username', json.loads(task['summary'])['blocked_reason'])
        self.assertEqual(db.many('SELECT * FROM runs'), [])
        self.assertEqual(db.many('SELECT * FROM test_cases'), [])
        self.session.request.assert_not_called()

    def test_playwright_failure_is_reported_with_its_run(self):
        self.run_passes = False
        task = self.submit()
        self.assertEqual(task['status'], 'FAILED')
        summary = json.loads(task['summary'])
        self.assertEqual(summary['execution']['counts']['FAIL'], 1)
        self.assertEqual(summary['execution']['status'], 'FAILED')
        self.assertIn('Playwright', task['error'])

    def test_plan_without_outcome_assertion_is_not_run(self):
        self.plan['cases'][0]['automation']['actions'] = [{'action': 'navigate', 'url': '/login'}, *self.login_actions]
        task = self.submit()
        self.assertEqual(task['status'], 'FAILED')
        self.assertIn('assert', task['error'])
        self.assertEqual(db.many('SELECT * FROM runs'), [])

    def test_failed_browser_action_is_supplied_to_next_decision(self):
        self.session.request.side_effect = [
            {'snapshot': self.start, 'performed': [], 'error': 'Locator matched two controls', 'mutation_outcome': 'not_started'},
            {'snapshot': self.destination, 'performed': self.login_actions},
        ]
        self.responses.insert(1, {'summary': 'Use the unique data-test locator.', 'actions': self.login_actions})
        task = self.submit()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(self.requests[1]['last_error'], 'Locator matched two controls')
        self.assertEqual(self.requests[2]['observation']['url'], self.destination['url'])

    def test_reset_completion_and_current_session_are_sent_to_next_decision(self):
        self.session.request.side_effect = [
            {'snapshot': self.destination, 'performed': self.login_actions},
            {'snapshot': self.start},
            {'snapshot': self.destination, 'performed': self.login_actions},
        ]
        self.responses = [
            {'summary': 'Explore the first scenario.', 'scenarios': ['Login'], 'actions': self.login_actions},
            {'summary': 'Start an independent scenario.', 'reset_browser': True},
            {'summary': 'Explore the next scenario on the clean page.', 'actions': self.login_actions},
            {'summary': 'All requested outcomes were observed.', 'done': True}, self.plan,
        ]
        task = self.submit(execution_mode='generate')
        self.assertEqual(task['status'], 'READY', task['error'])
        next_turn = self.requests[2]
        self.assertEqual(next_turn['browser_state']['last_command_result']['command'], 'reset')
        self.assertEqual(next_turn['browser_state']['last_command_result']['status'], 'completed')
        self.assertTrue(next_turn['browser_state']['fresh'])
        self.assertEqual(len(next_turn['current_session_actions']), 1)
        self.assertGreater(len(next_turn['performed_actions']), 1)
        self.assertIn('reset', next_turn['activity'][-1]['message'])

    def test_unknown_write_stops_before_replanning_reset_or_final_run(self):
        self.session.request.return_value = {
            'snapshot': self.start, 'performed': self.login_actions[:2],
            'error': 'Submit response timed out', 'mutation_outcome': 'unknown',
        }
        task = self.submit()
        self.assertEqual(task['status'], 'NEEDS_INPUT')
        self.assertIn('reconcile owned', json.loads(task['summary'])['blocked_reason'])
        self.assertEqual(len(self.requests), 1)
        self.session.request.assert_called_once()
        self.assertEqual(db.many('SELECT * FROM runs'), [])
        self.assertEqual(db.many('SELECT * FROM test_cases'), [])

    def test_missing_mutation_metadata_is_unknown_not_permission_to_retry(self):
        self.session.request.return_value = {'snapshot': self.start, 'performed': [], 'error': 'Connection lost'}
        task = self.submit()
        self.assertEqual(task['status'], 'NEEDS_INPUT')
        self.assertEqual(len(self.requests), 1)

    def test_transport_timeout_during_write_requires_reconciliation(self):
        self.session.request.side_effect = TimeoutError('Browser session did not respond')
        task = self.submit()
        self.assertEqual(task['status'], 'NEEDS_INPUT')
        self.assertIn('reconcile owned', json.loads(task['summary'])['blocked_reason'])
        self.assertEqual(len(self.requests), 1)

    def test_read_recovery_is_bounded_even_when_model_keeps_retrying(self):
        self.session.request.return_value = {'snapshot': self.start, 'performed': [],
                                            'error': 'Ambiguous control', 'mutation_outcome': 'not_started'}
        self.responses = [self.responses[0], self.responses[0], self.responses[0]]
        task = self.submit()
        self.assertEqual(task['status'], 'FAILED')
        self.assertIn('recovery budget exhausted', task['error'])
        self.assertEqual(self.session.request.call_count, 2)

    def test_budget_expiring_during_model_call_prevents_browser_dispatch(self):
        with patch.object(ui_agent, 'monotonic', side_effect=[0, 0, 1201]):
            task = self.submit()
        self.assertEqual(task['status'], 'FAILED')
        self.assertIn('wall-time budget exhausted', task['error'])
        self.session.request.assert_not_called()

    def test_context_manifest_matches_task_sources_role_and_exact_prompt(self):
        from testagent.context import content_hash
        import hashlib
        task = self.submit(execution_mode='generate')
        manifest = self.requests[0]['context_manifest']
        self.assertEqual(manifest['task_id'], task['id'])
        self.assertEqual(manifest['role'], 'ui_automation')
        self.assertEqual(manifest['usage_status'], 'UNKNOWN')
        self.assertEqual(manifest['observation_sha256'], content_hash(self.requests[0]['observation']))
        self.assertEqual(manifest['prompt_sha256'], hashlib.sha256(self.instructions[0].encode('utf-8')).hexdigest())
        self.assertEqual(json.loads(task['summary'])['context_manifest']['task_id'], task['id'])

    def test_production_policy_applies_before_any_live_browser_action(self):
        self.client.patch('/api/projects/' + self.project, json={'base_url': self.start['url'], 'environment': 'production'})
        result = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'function': 'ui_automation', 'prompt': 'Log in to the website.'})
        self.assertEqual(result.status_code, 403)
        ui_agent.BrowserSession.assert_not_called()
        self.assertEqual(db.many('SELECT * FROM tasks'), [])


class DemoPage(BaseHTTPRequestHandler):
    def do_GET(self):
        content = b'''<!doctype html><html><title>Locator fixture</title><body>
        <section data-test="login"><input placeholder="Username"><input placeholder="Password" type="password">
        <button data-test="sign-in" onclick="localStorage.setItem('signed_in','yes'); document.cookie='signed_in=yes'; document.querySelector('#result').textContent='Signed in'; history.pushState({},'', '/dashboard')">Sign in</button></section>
        <h2 id="result" data-test="result">Waiting</h2>
        <section data-test="one"><button>Continue</button></section><section data-test="two"><button>Continue</button></section>
        <button>Save</button><button>Save settings</button>
        <script>if(localStorage.getItem('signed_in') || document.cookie.includes('signed_in=yes')) document.querySelector('#result').textContent='Restored session';</script>
        </body></html>'''
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass


class TypeScriptBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.website = ThreadingHTTPServer(('127.0.0.1', 0), DemoPage)
        cls.thread = threading.Thread(target=cls.website.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.website.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.website.shutdown()
        cls.website.server_close()
        cls.thread.join(timeout=3)

    def test_stateful_browser_handles_custom_test_attributes_and_observes_after_click(self):
        with BrowserSession(self.url, self.url) as session:
            button = next(e for e in session.initial['snapshot']['elements'] if e.get('testid') == 'sign-in')
            self.assertEqual(button['suggested_target'], {'testid': 'sign-in', 'test_attribute': 'data-test'})
            self.assertEqual(button['match_count'], 1)
            result = session.request({'command': 'act', 'automation': {'actions': [
                {'action': 'fill', 'target': {'placeholder': 'Username'}, 'value': 'demo'},
                {'action': 'click', 'target': button['suggested_target']},
                {'action': 'assert_text', 'target': {'testid': 'result', 'test_attribute': 'data-test'}, 'value': 'Signed in'},
            ]}})
            self.assertFalse(result.get('error'), result)
            self.assertTrue(result['snapshot']['url'].endswith('/dashboard'))
            self.assertIn('Signed in', result['snapshot']['text'])
        self.assertIsNotNone(session.proc.poll())

    def test_scoped_and_exact_locators_compile_and_run_with_matching_behavior(self):
        automation = {'actions': [
            {'action': 'navigate', 'url': '/'},
            {'action': 'assert_visible', 'target': {'role': 'button', 'name': 'Continue', 'scope': {'testid': 'one', 'test_attribute': 'data-test'}}},
            {'action': 'click', 'target': {'role': 'button', 'name': 'Save'}},
        ]}
        source = invoke_browser('compile', {'baseUrl': self.url, 'title': 'Scoped locator', 'automation': automation})['source']
        self.assertIn('exact: true', source)
        self.assertIn('.toHaveCount(1,', source)
        self.assertIn('[data-test=', source)
        with tempfile.TemporaryDirectory() as directory:
            result = invoke_browser('execute', {'baseUrl': self.url, 'caseId': 'scope-test', 'artifactDir': directory, 'automation': automation}, timeout=45)
            self.assertEqual(result['status'], 'PASS', result)
            self.assertIn('scope-test.spec.ts', result['artifacts'])
            self.assertTrue(any(name.endswith('-trace.zip') for name in result['artifacts']))

    def test_reset_clears_browser_state_between_independent_scenarios(self):
        with BrowserSession(self.url, self.url) as session:
            result = session.request({'command': 'act', 'automation': {'actions': [
                {'action': 'fill', 'target': {'placeholder': 'Username'}, 'value': 'demo'},
                {'action': 'click', 'target': {'testid': 'sign-in', 'test_attribute': 'data-test'}},
                {'action': 'navigate', 'url': '/'},
            ]}})
            self.assertIn('Restored session', result['snapshot']['text'])
            reset = session.request({'command': 'reset'})
            self.assertFalse(reset.get('error'), reset)
            self.assertIn('Waiting', reset['snapshot']['text'])
            self.assertNotIn('Restored session', reset['snapshot']['text'])

    def test_ambiguous_locator_fails_instead_of_clicking_the_first_control(self):
        with BrowserSession(self.url, self.url) as session:
            result = session.request({'command': 'act', 'automation': {'actions': [{'action': 'click', 'target': {'role': 'button', 'name': 'Continue'}}]}}, timeout=30)
            self.assertIn('Received: 2', result['error'])
            self.assertEqual(result['performed'], [])
            self.assertEqual(result['mutation_outcome'], 'not_started')
            self.assertEqual(result['failed_action']['action'], 'click')

    def test_group_failure_after_mutation_cannot_be_replayed_as_not_started(self):
        with BrowserSession(self.url, self.url) as session:
            result = session.request({'command': 'act', 'automation': {'actions': [
                {'action': 'fill', 'target': {'placeholder': 'Username'}, 'value': 'demo'},
                {'action': 'assert_visible', 'target': {'id': 'missing-oracle'}},
            ]}}, timeout=30)
            self.assertTrue(result.get('error'))
            self.assertEqual(result['mutation_outcome'], 'unknown')
            self.assertEqual(result['failed_action']['action'], 'assert_visible')
            self.assertEqual(len(result['performed']), 1)


if __name__ == '__main__':
    unittest.main()
