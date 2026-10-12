import json
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from testagent import agent_validation, api as api_module, db, planner
from testagent.config import settings
from testagent.knowledge import add_source


class OrchestratorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        config = replace(settings, data_dir=Path(self.directory.name))
        account = Mock()
        account.resolve.return_value = {'provider': 'codex', 'model': 'model-a', 'effort': 'high'}
        self.complete = Mock(side_effect=[
            {'function': 'performance', 'reason': 'The requested outcome is a concurrent-user workload assessment.'},
            {'summary': 'Assess the login API with a workload of 2,000 concurrent users.', 'findings': []},
        ])
        self.patches = [patch.object(db, 'settings', config),
                        patch.object(api_module, 'provider_manager', account),
                        patch.object(planner, 'complete_json', self.complete),
                        patch('testagent.subagents.settings', replace(settings, subagent_workers=3)),
                        patch('testagent.subagents._SLOTS', threading.BoundedSemaphore(3)),
                        patch.object(agent_validation, 'browser_runner_available', return_value=True)]
        for item in self.patches:
            item.start()
        self.client = TestClient(api_module.app)
        self.client.__enter__()
        self.project = self.client.post('/api/projects', json={'name': 'Routing tests', 'environment': 'local'}).json()['id']

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def submit(self, **options):
        response = self.client.post('/api/agent/tasks', json={
            'project_id': self.project,
            'prompt': 'Kiểm tra API login chịu được 2,000 concurrent users không.',
            **options,
        })
        self.assertEqual(response.status_code, 202, response.text)
        return self.client.get('/api/agent/tasks/' + response.json()['id']).json()

    def choose(self, function):
        self.complete.side_effect = [
            {'function': function, 'reason': 'Choose the specialist for the requested deliverable.'},
            {'summary': 'Analysis based on the supplied evidence.', 'findings': []},
        ]

    def add_case(self, project=None):
        case_id = db.uid()
        db.execute('''INSERT INTO test_cases
            (id, project_id, title, level, type, priority, preconditions, steps, expected, source_ids, api_request, created_at)
            VALUES (?, ?, 'API health', 'api', 'positive', 'high', '[]', '["Request health"]', '["HTTP 200"]', '[]', ?, ?)''',
                   (case_id, project or self.project, json.dumps({'method': 'GET', 'path': '/health', 'expected_status': 200}), db.now()))
        return case_id

    def add_run(self, status='COMPLETED', project=None, with_results=True):
        run_id, case_id = db.uid(), self.add_case(project)
        db.execute('INSERT INTO runs (id, project_id, status, requested_at, summary) VALUES (?, ?, ?, ?, ?)',
                   (run_id, project or self.project, status, db.now(), '{"total":1,"counts":{"PASS":1}}'))
        if with_results:
            db.execute('INSERT INTO run_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                       (db.uid(), run_id, case_id, 'PASS', 10, None, 'HTTP 200', '[]'))
        return run_id

    def test_default_routes_to_specialist_with_pinned_selection_and_metadata(self):
        task = self.submit()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(task['intent'], 'performance')
        self.assertEqual(task['skill_file'], 'performance.md')
        self.assertEqual(task['orchestration']['function'], 'performance')
        self.assertEqual(task['orchestration']['source'], 'ai')
        self.assertEqual(self.complete.call_count, 2)
        for call in self.complete.call_args_list:
            self.assertEqual(call.args[2:], ('codex', 'model-a', 'high'))
        routing = json.loads(self.complete.call_args_list[0].args[1])
        self.assertEqual(routing['function'], 'orchestrator')
        self.assertEqual(routing['context']['sources'], [])
        self.assertNotIn('orchestrator', {item['id'] for item in routing['available_functions']})
        self.assertIn('Active phase: final. Return AgentRoute only.', self.complete.call_args_list[0].args[0])
        self.assertEqual(json.loads(self.complete.call_args_list[1].args[1])['function'], 'performance')
        self.assertEqual(json.loads(task['summary'])['skill_id'], 'performance')
        self.assertEqual(self.client.get(f'/api/projects/{self.project}/tasks').json()[0]['orchestration'], task['orchestration'])

    def test_auto_and_orchestrator_are_supported_explicit_choices(self):
        for function in ('auto', 'orchestrator'):
            with self.subTest(function=function):
                self.choose('test_plan')
                task = self.submit(function=function)
                self.assertEqual(task['status'], 'COMPLETED', task['error'])
                self.assertEqual(task['intent'], 'test_plan')

    def test_explicit_specialist_bypasses_ai_routing(self):
        self.complete.side_effect = [{'summary': 'Manual performance analysis of the supplied goal.'}]
        task = self.submit(function='performance')
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(task['orchestration'], {})
        self.assertEqual(self.complete.call_count, 1)
        self.assertEqual(json.loads(self.complete.call_args.args[1])['function'], 'performance')

    def test_missing_required_context_requests_input_before_specialist_call(self):
        for function in ('repo_under', 'unit_test', 'regression', 'report', 'defect_analysis', 'case_review', 'automation_builder', 'run_tests', 'ui_automation'):
            with self.subTest(function=function):
                self.complete.reset_mock()
                self.choose(function)
                task = self.submit()
                self.assertEqual(task['status'], 'NEEDS_INPUT', task['error'])
                self.assertEqual(task['intent'], function)
                self.assertTrue(json.loads(task['summary'])['blocked_reason'])
                self.assertEqual(self.complete.call_count, 1)
                self.assertEqual(db.many('SELECT * FROM runs'), [])

    def test_repository_context_is_available_to_routing_and_specialist(self):
        add_source(self.project, 'code', 'app.py', 'repo:app.py', 'def login(): pass')
        self.choose('repo_under')
        task = self.submit()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(json.loads(self.complete.call_args_list[0].args[1])['context']['sources'], [{'kind': 'code', 'count': 1}])
        self.assertTrue(json.loads(self.complete.call_args_list[1].args[1])['evidence']['repository_files'])

    def test_selected_cases_are_forwarded_only_to_cases_specialist(self):
        case_id = self.add_case()
        self.choose('case_review')
        task = self.submit(case_ids=[case_id, case_id])
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(task['orchestration']['case_ids'], [case_id])
        self.assertEqual(json.loads(self.complete.call_args_list[1].args[1])['evidence']['test_cases'][0]['id'], case_id)

    def test_report_uses_latest_finished_run_and_explicit_run_overrides_it(self):
        first_run = self.add_run()
        latest_run = self.add_run(status='FAILED')
        for requested_run, expected_run in ((None, latest_run), (first_run, first_run)):
            with self.subTest(run=requested_run):
                self.choose('report')
                task = self.submit(**({'run_id': requested_run} if requested_run else {}))
                self.assertEqual(task['status'], 'COMPLETED', task['error'])
                self.assertEqual(task['orchestration']['run_id'], expected_run)
                self.assertEqual(json.loads(task['summary'])['run_id'], expected_run)
                self.assertEqual(self.client.get(f"/api/agent/tasks/{task['id']}/report").status_code, 200)

    def test_unfinished_or_empty_run_requests_input(self):
        for status, results in (('RUNNING', True), ('COMPLETED', False)):
            with self.subTest(status=status):
                run_id = self.add_run(status=status, with_results=results)
                self.complete.reset_mock()
                self.choose('report')
                task = self.submit(run_id=run_id)
                self.assertEqual(task['status'], 'NEEDS_INPUT', task['error'])
                self.assertEqual(self.complete.call_count, 1)

    def test_foreign_run_and_case_ids_are_rejected_before_routing(self):
        other_project = self.client.post('/api/projects', json={'name': 'Other project'}).json()['id']
        for options in ({'run_id': self.add_run(project=other_project)}, {'case_ids': [self.add_case(other_project)]}):
            response = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'prompt': 'Analyze existing tests', **options})
            self.assertEqual(response.status_code, 422, response.text)
        self.complete.assert_not_called()
        self.assertEqual(db.many('SELECT * FROM tasks'), [])

    def test_invalid_or_recursive_delegation_fails_without_dispatch(self):
        for function in ('orchestrator', 'unknown', '../config'):
            with self.subTest(function=function):
                self.complete.reset_mock()
                self.choose(function)
                task = self.submit()
                self.assertEqual(task['status'], 'FAILED')
                self.assertTrue(task['error'])
                self.assertEqual(self.complete.call_count, 1)

    def test_extra_commands_in_route_response_are_rejected(self):
        self.complete.side_effect = [{'function': 'test_plan', 'reason': 'Plan the requested tests.', 'actions': ['execute shell']}]
        task = self.submit()
        self.assertEqual(task['status'], 'FAILED')
        self.assertEqual(self.complete.call_count, 1)

    def test_browser_specialist_receives_execution_options(self):
        self.client.patch('/api/projects/' + self.project, json={'base_url': 'http://localhost:9000', 'environment': 'local'})
        self.choose('ui_automation')
        with patch.object(planner, '_run_ui_task') as browser_task:
            self.submit(execution_mode='generate', run_mode='parallel', workers=2)
        self.assertEqual(browser_task.call_args.args[-3:], ('generate', 'parallel', 2))
        self.assertEqual(browser_task.call_args.args[4].id, 'ui_automation')
        self.assertEqual(self.complete.call_count, 1)

    def test_automatic_browser_route_enforces_production_guard(self):
        self.client.patch('/api/projects/' + self.project, json={'base_url': 'https://example.test', 'environment': 'production'})
        self.choose('ui_automation')
        with patch.object(agent_validation, 'settings', replace(settings, allow_production_execution=False)), patch.object(planner, '_run_ui_task') as browser_task:
            task = self.submit()
        self.assertEqual(task['status'], 'FAILED')
        self.assertIn('production', task['error'])
        browser_task.assert_not_called()

    def test_generate_mode_cannot_start_execution_of_saved_cases(self):
        self.choose('run_tests')
        task = self.submit(case_ids=[self.add_case()], execution_mode='generate')
        self.assertEqual(task['status'], 'NEEDS_INPUT')
        self.assertEqual(db.many('SELECT * FROM runs'), [])

    def test_execution_route_uses_deterministic_runner_without_second_ai_call(self):
        self.client.patch('/api/projects/' + self.project, json={'base_url': 'http://localhost:9000', 'environment': 'local'})
        self.choose('run_tests')
        def finish(run_id):
            db.execute("UPDATE runs SET status='COMPLETED', summary=? WHERE id=?",
                       ('{"total":1,"counts":{"PASS":1}}', run_id))
        with patch.object(planner, 'execute_run', side_effect=finish) as execute:
            task = self.submit(case_ids=[self.add_case()], execution_mode='run', run_mode='parallel', workers=2)
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(self.complete.call_count, 1)
        execute.assert_called_once()
        self.assertEqual(json.loads(task['summary'])['execution']['counts']['PASS'], 1)

    def test_database_migration_is_idempotent_and_old_tasks_have_empty_route(self):
        db.init_db()
        db.init_db()
        self.complete.side_effect = [{'summary': 'Manual analysis remains available for existing clients.'}]
        task = self.submit(function='test_plan')
        self.assertEqual(task['orchestration'], {})
        self.assertEqual(task['status'], 'COMPLETED', task['error'])

    def team(self, lead='test_plan', helpers=('security', 'performance')):
        return {'function': lead, 'reason': 'Combine independent risk analyses into the requested deliverable.',
                'sub_tasks': [{'function': role, 'prompt': f'Analyze only the {role} risks and essential missing inputs.'} for role in helpers]}

    def test_independent_sub_agents_overlap_share_inspection_and_feed_lead(self):
        barrier = threading.Barrier(2)
        lead_requests = []
        source = add_source(self.project, 'document', 'Rules', 'test:rules', 'Login uses authorized test accounts.')
        def complete(system, user, *selection):
            self.assertEqual(selection, ('codex', 'model-a', 'high'))
            request = json.loads(user)
            function = request['function']
            if function == 'orchestrator':
                return self.team()
            if function in {'security', 'performance'}:
                self.assertIn('subagent-handoff.md', system)
                self.assertIn('delegation', request['evidence'])
                barrier.wait(timeout=5)
                return {'summary': f'Independent {function} analysis with explicit gaps.',
                        'findings': [{'title': 'Evidence-backed concern', 'detail': 'A focused supporting finding.',
                                      'evidence_ids': [source, 'invented-source']}],
                        'recommendations': ['Confirm the relevant acceptance threshold.']}
            lead_requests.append(request)
            return {'summary': 'The lead reconciles both independent analyses into one test plan.'}
        self.complete.side_effect = complete
        with patch.object(planner, '_website_context', return_value={'available': True, 'text': 'Shared snapshot'}) as inspect:
            task = self.submit()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(self.complete.call_count, 4)
        inspect.assert_called_once()
        children = task['sub_tasks']
        self.assertEqual({child['intent'] for child in children}, {'security', 'performance'})
        self.assertTrue(all(child['status'] == 'COMPLETED' and child['parent_task_id'] == task['id'] for child in children))
        self.assertEqual(len(self.client.get(f'/api/projects/{self.project}/tasks').json()), 1)
        for child in children:
            self.assertEqual(self.client.get('/api/agent/tasks/' + child['id']).json()['parent_task_id'], task['id'])
            self.assertEqual(json.loads(child['summary'])['findings'][0]['evidence_ids'], [source])
            self.assertIn('subagent-handoff.md', json.loads(child['summary'])['skills'])
        handoffs = lead_requests[0]['evidence']['sub_agent_results']
        self.assertEqual([item['function'] for item in handoffs], ['security', 'performance'])
        self.assertTrue(all(item['findings'][0]['evidence_ids'] == [source] for item in handoffs))
        self.assertEqual(task['orchestration']['metrics']['completed'], 2)
        self.assertEqual(db.many('SELECT * FROM runs'), [])
        self.assertEqual(db.many('SELECT * FROM test_cases'), [])

    def test_sub_agent_failure_preserves_children_and_prevents_false_completion(self):
        def complete(system, user, *selection):
            function = json.loads(user)['function']
            if function == 'orchestrator':
                return self.team()
            if function == 'security':
                raise RuntimeError('Provider quota exceeded')
            self.assertEqual(function, 'performance', 'The lead must not run after a worker failure')
            return {'summary': 'Capacity thresholds need confirmation.'}
        self.complete.side_effect = complete
        task = self.submit()
        self.assertEqual(task['status'], 'FAILED')
        self.assertIn('quota exceeded', task['error'])
        self.assertEqual({child['status'] for child in task['sub_tasks']}, {'FAILED', 'COMPLETED'})
        self.assertEqual(self.complete.call_count, 3)
        self.assertEqual(task['orchestration']['metrics']['completed'], 1)

    def test_sub_agents_require_available_analysis_roles_without_duplicates(self):
        for helpers in (('orchestrator',), ('run_tests',), ('ui_automation',), ('gen_testcase',),
                        ('unknown',), ('test_plan',), ('security', 'security')):
            with self.subTest(helpers=helpers):
                self.complete.reset_mock()
                self.complete.side_effect = [self.team(helpers=helpers)]
                task = self.submit()
                self.assertEqual(task['status'], 'FAILED')
                self.assertEqual(self.complete.call_count, 1)
                self.assertEqual(task['sub_tasks'], [])

    def test_sub_agent_budget_and_single_mode_are_enforced_before_dispatch(self):
        for options, helpers in (({}, ('security', 'performance', 'test_data', 'exploratory')),
                                 ({'agent_mode': 'single'}, ('security',)),
                                 ({'case_ids': [self.add_case()]}, ('security',))):
            self.complete.reset_mock()
            self.complete.side_effect = [self.team(lead='run_tests' if options.get('case_ids') else 'test_plan', helpers=helpers)]
            task = self.submit(**options)
            self.assertEqual(task['status'], 'FAILED')
            self.assertEqual(self.complete.call_count, 1)
        self.complete.side_effect = [{'function': 'test_plan', 'reason': 'A single plan is sufficient.', 'sub_tasks': []},
                                     {'summary': 'One specialist prepares the requested plan.'}]
        task = self.submit(agent_mode='single')
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(task['sub_tasks'], [])
        request = json.loads(self.complete.call_args_list[-2].args[1])
        self.assertEqual(request['max_sub_tasks'], 0)

    def test_missing_helper_prerequisite_blocks_before_any_worker_call(self):
        self.complete.side_effect = [self.team(helpers=('repo_under',))]
        task = self.submit()
        self.assertEqual(task['status'], 'NEEDS_INPUT')
        self.assertIn('mã nguồn', json.loads(task['summary'])['blocked_reason'])
        self.assertEqual(self.complete.call_count, 1)
        self.assertEqual(task['sub_tasks'], [])

    def test_helpers_keep_selected_case_and_run_scope_when_lead_needs_neither(self):
        run_id = self.add_run()
        case_id = self.add_case()
        self.add_run(status='FAILED')
        helper_requests = {}
        def complete(system, user, *selection):
            request = json.loads(user)
            if request['function'] == 'orchestrator':
                return self.team(helpers=('case_review', 'defect_analysis'))
            if request['function'] != 'test_plan':
                helper_requests[request['function']] = request
            return {'summary': 'A scoped analysis of the selected test evidence.'}
        self.complete.side_effect = complete
        task = self.submit(case_ids=[case_id], run_id=run_id)
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(helper_requests['case_review']['evidence']['test_cases'][0]['id'], case_id)
        self.assertEqual(helper_requests['defect_analysis']['evidence']['run']['id'], run_id)

    def test_parallel_workers_respect_global_concurrency_limit(self):
        lock = threading.Lock()
        active, peak = 0, 0
        def complete(system, user, *selection):
            nonlocal active, peak
            function = json.loads(user)['function']
            if function == 'orchestrator':
                return self.team(helpers=('security', 'performance', 'test_data'))
            if function != 'test_plan':
                with lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep(0.03)
                with lock:
                    active -= 1
            return {'summary': 'A bounded independent analysis of the requested scope.'}
        self.complete.side_effect = complete
        with patch('testagent.subagents._SLOTS', threading.BoundedSemaphore(1)):
            task = self.submit()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(peak, 1)

    def test_generation_lead_consumes_helpers_and_creates_cases_only_once(self):
        def complete(system, user, *selection):
            request = json.loads(user)
            if request['function'] == 'orchestrator':
                return self.team(lead='gen_testcase', helpers=('security',))
            if request['function'] == 'security':
                return {'summary': 'Invalid credentials must not establish a session.',
                        'recommendations': ['Confirm the specific error marker before automation.']}
            self.assertEqual(request['function'], 'gen_testcase')
            self.assertEqual(request['evidence']['sub_agent_results'][0]['function'], 'security')
            return {'intent': 'test_generation', 'summary': 'Drafted one negative case from the supplied rule.',
                    'cases': [{'title': 'Reject an invalid password', 'level': 'ui', 'type': 'negative',
                               'priority': 'high', 'steps': ['Submit an invalid password using an authorized test account.'],
                               'expected': ['No authenticated session is created.'], 'source_ids': []}]}
        self.complete.side_effect = complete
        task = self.submit(execution_mode='generate')
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        cases = db.many('SELECT * FROM test_cases')
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['task_id'], task['id'])
        self.assertEqual(db.many('SELECT * FROM runs'), [])
        self.assertEqual(len(task['sub_tasks']), 1)

    def test_malformed_worker_output_is_not_handed_off_to_lead(self):
        def complete(system, user, *selection):
            function = json.loads(user)['function']
            if function == 'orchestrator':
                return self.team(helpers=('security',))
            self.assertEqual(function, 'security')
            return {'summary': 'short', 'findings': []}
        self.complete.side_effect = complete
        task = self.submit()
        self.assertEqual(task['status'], 'FAILED')
        self.assertEqual(task['sub_tasks'][0]['status'], 'FAILED')
        self.assertEqual(self.complete.call_count, 2)

    def test_handoff_bounds_context_and_keeps_critical_findings(self):
        findings = [{'title': f'Observation {index}', 'detail': 'A long observation. ' * 120,
                     'severity': 'critical' if index == 19 else 'info', 'evidence_ids': []} for index in range(20)]
        def complete(system, user, *selection):
            request = json.loads(user)
            if request['function'] == 'orchestrator':
                return self.team(helpers=('security',))
            if request['function'] == 'security':
                return {'summary': 'Useful facts and limitations. ' * 100, 'findings': findings,
                        'recommendations': ['A lengthy recommendation. ' * 50] * 20}
            handoff = request['evidence']['sub_agent_results'][0]
            self.assertTrue(handoff['condensed'])
            self.assertEqual(handoff['finding_count'], 20)
            self.assertEqual(handoff['findings'][0]['severity'], 'critical')
            self.assertLess(len(json.dumps(handoff, ensure_ascii=False)), 6000)
            return {'summary': 'Prioritize the critical concern and acknowledge condensed evidence.'}
        self.complete.side_effect = complete
        task = self.submit()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(len(json.loads(task['sub_tasks'][0]['summary'])['findings']), 20)

    def test_finished_task_is_not_generated_again_on_repeated_delivery(self):
        self.complete.side_effect = None
        self.complete.return_value = {'summary': 'Assess capacity based on the supplied workload.'}
        task = self.submit(function='performance')
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.complete.reset_mock()
        planner.run_task(task['id'], self.project, task['prompt'], 'performance')
        self.complete.assert_not_called()

    def test_concurrent_task_delivery_calls_the_specialist_only_once(self):
        task_id = db.uid()
        prompt = 'Assess the supplied workload.'
        db.execute('INSERT INTO tasks (id,project_id,prompt,intent,status,created_at) VALUES (?,?,?,?,?,?)',
                   (task_id, self.project, prompt, 'performance', 'CREATED', db.now()))
        entered, release = threading.Event(), threading.Event()
        def complete(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test worker was not released')
            return {'summary': 'One specialist analyzes the supplied workload.'}
        self.complete.side_effect = complete
        worker = threading.Thread(target=planner.run_task, args=(task_id, self.project, prompt, 'performance'))
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            planner.run_task(task_id, self.project, prompt, 'performance')
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.complete.call_count, 1)
        self.assertEqual(db.one('SELECT status FROM tasks WHERE id=?', (task_id,))['status'], 'COMPLETED')

    def test_sub_agent_only_hands_off_evidence_visible_in_its_compact_findings(self):
        from testagent.orchestrator import RoutedSubTask
        from testagent.skills import get_skill
        from testagent.subagents import execute_sub_agents
        parent_id = db.uid()
        db.execute('INSERT INTO tasks (id,project_id,prompt,intent,status,created_at) VALUES (?,?,?,?,?,?)',
                   (parent_id, self.project, 'Plan independent checks', 'test_plan', 'ANALYZING', db.now()))
        plan = RoutedSubTask(get_skill('security'), 'Analyze authentication security risks.', None, [])
        def work(task_id, plan):
            payload = {'summary': 'Only one evidence item is included in this handoff.',
                       'findings': [{'title': 'Supported finding', 'detail': 'A supplied observation.',
                                     'evidence_ids': ['visible-evidence']}]}
            planner._store_analysis(task_id, plan.skill, payload, {'visible-evidence', 'unseen-evidence'}, None)
            return {'visible-evidence', 'unseen-evidence'}
        handoffs, ids = execute_sub_agents(parent_id, self.project, [plan], 'codex', 'model-a', 'high', work)
        self.assertEqual(ids, {'visible-evidence'})
        self.assertEqual(handoffs[0]['findings'][0]['evidence_ids'], ['visible-evidence'])

    def test_case_source_ids_cannot_reference_run_results_or_foreign_sources(self):
        run_id = self.add_run()
        result_id = db.one('SELECT id FROM run_results WHERE run_id=?', (run_id,))['id']
        source = add_source(self.project, 'document', 'Rules', 'fixture:rules', 'Login must reject wrong passwords.')
        foreign_project = self.client.post('/api/projects', json={'name': 'Foreign sources'}).json()['id']
        foreign_source = add_source(foreign_project, 'document', 'Other rules', 'fixture:other', 'Foreign requirements.')
        task_id = db.uid()
        db.execute('INSERT INTO tasks (id,project_id,prompt,intent,status,created_at) VALUES (?,?,?,?,?,?)',
                   (task_id, self.project, 'Generate a case', 'gen_testcase', 'ANALYZING', db.now()))
        payload = {'intent': 'test_generation', 'summary': 'One supported negative test.',
                   'cases': [{'title': 'Reject wrong password', 'level': 'ui', 'type': 'negative',
                              'priority': 'high', 'steps': ['Submit wrong password.'],
                              'expected': ['No session is created.'], 'source_ids': [source, result_id, foreign_source]}]}
        from testagent.skills import get_skill
        planner._store_test_cases(task_id, self.project, get_skill('gen_testcase'), payload,
                                  {source, result_id, foreign_source})
        case = db.decode_case(db.one('SELECT * FROM test_cases WHERE task_id=?', (task_id,)))
        self.assertEqual(case['source_ids'], [source])

    def test_empty_helper_plan_has_no_database_or_worker_side_effects(self):
        from testagent.subagents import execute_sub_agents
        worker = Mock()
        self.assertEqual(execute_sub_agents('missing', self.project, [], None, None, None, worker), ([], set()))
        worker.assert_not_called()
        self.assertEqual(db.many('SELECT id FROM tasks'), [])

    def test_helper_runtime_rejects_invalid_roles_and_foreign_parent_before_inserts(self):
        from testagent.orchestrator import RoutedSubTask
        from testagent.skills import get_skill
        from testagent.subagents import execute_sub_agents
        worker = Mock()
        for role_ids in [('run_tests',), ('security', 'security'),
                         ('security', 'performance', 'test_data', 'exploratory'), ('security',)]:
            with self.subTest(roles=role_ids):
                plans = [RoutedSubTask(get_skill(role), 'Analyze only supplied evidence.', None, []) for role in role_ids]
                with self.assertRaises(ValueError):
                    execute_sub_agents('missing-parent', self.project, plans, None, None, None, worker)
        worker.assert_not_called()
        self.assertEqual(db.many('SELECT id FROM tasks'), [])


if __name__ == '__main__':
    unittest.main()
