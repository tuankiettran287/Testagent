import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from testagent import api as api_module, db, planner
from testagent.browser_bridge import BrowserRunnerError
from testagent.config import settings
from testagent.knowledge import add_source
from testagent.skills import SKILLS


class OptionalContextTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        config = replace(settings, data_dir=Path(self.directory.name))
        account = Mock()
        account.resolve.return_value = {'provider': 'codex', 'model': 'native-model'}
        self.contexts, self.instructions = [], []
        self.snapshot = {'url': 'http://localhost:9000/login', 'title': 'Demo login', 'http_status': 200,
                         'text': 'Sign in Email Password Log in',
                         'elements': [{'tag': 'input', 'id': 'email', 'label': 'Email', 'required': True, 'visible': True},
                                      {'tag': 'input', 'id': 'secret', 'visible': False}]}
        self.patches = [patch.object(db, 'settings', config), patch.object(api_module, 'provider_manager', account),
                        patch.object(planner, 'invoke_browser', return_value=self.snapshot),
                        patch.object(planner, 'complete_json', side_effect=self.generate)]
        for item in self.patches:
            item.start()
        self.client = TestClient(api_module.app)
        self.client.__enter__()
        self.project = self.client.post('/api/projects', json={'name': 'Optional sources'}).json()['id']

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def generate(self, system, request, provider, model, effort=None):
        self.instructions.append(system)
        context = json.loads(request)
        self.contexts.append(context)
        if context['function'] in {'test_plan', 'exploratory', 'requirement_under'}:
            return {'summary': 'A plan based on the supplied testing goal.', 'findings': []}
        return {'intent': 'test_generation', 'summary': 'Check the visible login controls.', 'cases': [
            {'title': 'Visible email input', 'level': 'ui', 'type': 'positive', 'priority': 'high',
             'steps': ['Open the supplied page and check the Email input'], 'expected': ['Email input is visible'],
             'source_ids': [source['source_id'] for source in context['evidence']['sources']] + ['invented-id']}
        ]}

    def create_task(self, skill='gen_testcase', prompt='Check the visible login controls.'):
        response = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'prompt': prompt, 'function': skill})
        self.assertEqual(response.status_code, 202, response.text)
        return self.client.get('/api/agent/tasks/' + response.json()['id']).json()

    def set_url(self, url='http://localhost:9000/login'):
        self.assertEqual(self.client.patch('/api/projects/' + self.project,
                         json={'base_url': url, 'environment': 'local'}).status_code, 200)

    def test_prompt_only_tasks_do_not_require_uploaded_sources(self):
        for skill in ('gen_testcase', 'ui_automation', 'api_test', 'test_plan', 'exploratory', 'requirement_under'):
            with self.subTest(skill=skill):
                task = self.create_task(skill)
                self.assertEqual(task['status'], 'COMPLETED', task['error'])
                self.assertEqual(self.contexts[-1]['evidence']['sources'], [])
                self.assertNotIn('website', self.contexts[-1]['evidence'])
        planner.invoke_browser.assert_not_called()
        self.assertEqual(db.many('SELECT * FROM sources'), [])

    def test_analysis_loads_shared_rules_and_records_actual_prompt_documents(self):
        task = self.create_task('test_plan')
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        prompt = self.instructions[-1]
        self.assertIn('instruction file: automation-core.md', prompt)
        self.assertIn('instruction file: test-plan.md', prompt)
        self.assertIn('Active phase: final. Return AgentAnalysis only.', prompt)
        self.assertNotIn('instruction file: automation-patterns.md', prompt)
        self.assertEqual(json.loads(task['summary'])['skills'], ['automation-core.md', 'test-plan.md'])
        self.assertEqual(self.client.get('/api/agent/skills/test_plan').json()['instruction_files'],
                         ['automation-core.md', 'test-plan.md'])

    def test_website_inspection_supplies_context_without_creating_sources(self):
        self.set_url()
        task = self.create_task('gen_testcase')
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        context = self.contexts[-1]
        self.assertEqual(context['project']['base_url'], 'http://localhost:9000/login')
        self.assertEqual(context['evidence']['sources'], [])
        website = context['evidence']['website']
        self.assertTrue(website['available'])
        self.assertEqual(website['title'], 'Demo login')
        self.assertEqual(website['http_status'], 200)
        self.assertEqual([element['id'] for element in website['elements']], ['email'])
        self.assertEqual(self.client.get(f'/api/projects/{self.project}/sources').json(), [])
        self.assertEqual(self.client.get(f'/api/projects/{self.project}/tests').json()[0]['source_ids'], [])
        self.assertEqual(planner.invoke_browser.call_args.args,
                         ('inspect', {'baseUrl': 'http://localhost:9000/login', 'path': 'http://localhost:9000/login'}))

    def test_uploaded_sources_supplement_website_and_keep_attribution(self):
        self.set_url()
        source = add_source(self.project, 'document', 'notes.md', 'upload:notes', 'Login uses an email and password.')
        task = self.create_task()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(self.contexts[-1]['evidence']['sources'][0]['source_id'], source)
        self.assertTrue(self.contexts[-1]['evidence']['website']['available'])
        cases = self.client.get(f'/api/projects/{self.project}/tests').json()
        self.assertEqual(cases[0]['source_ids'], [source])

    def test_same_origin_url_in_prompt_selects_page_without_following_other_links(self):
        self.set_url('http://localhost:9000')
        task = self.create_task(prompt='Notes at https://docs.example.test. Test http://localhost:9000/signin?mode=email')
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        self.assertEqual(planner.invoke_browser.call_args.args[1]['path'], 'http://localhost:9000/signin?mode=email')

    def test_external_link_does_not_change_project_target(self):
        self.set_url()
        self.create_task(prompt='Check login, compare the guide at https://outside.example.test')
        self.assertEqual(planner.invoke_browser.call_args.args[1]['path'], 'http://localhost:9000/login')

    def test_unavailable_website_does_not_reintroduce_source_requirement(self):
        self.set_url()
        planner.invoke_browser.side_effect = BrowserRunnerError('Connection refused')
        task = self.create_task()
        self.assertEqual(task['status'], 'COMPLETED', task['error'])
        website = self.contexts[-1]['evidence']['website']
        self.assertFalse(website['available'])
        self.assertEqual(website['error'], 'Connection refused')
        self.assertNotIn('elements', website)

    def test_code_and_run_functions_still_require_their_subject(self):
        self.set_url()
        for skill in ('repo_under', 'unit_test', 'regression', 'report', 'defect_analysis'):
            with self.subTest(skill=skill):
                self.assertEqual(self.create_task(skill)['status'], 'FAILED')
        planner.complete_json.assert_not_called()
        planner.invoke_browser.assert_not_called()

    def test_skill_metadata_does_not_make_sources_a_prerequisite(self):
        skills = self.client.get('/api/agent/skills').json()
        self.assertEqual({s['requires'] for s in skills}, {'none', 'code', 'run', 'cases'})
        self.assertTrue(all(s.requires == 'none' for s in SKILLS if s.id in {'gen_testcase', 'ui_automation', 'api_test', 'exploratory'}))


if __name__ == '__main__':
    unittest.main()
