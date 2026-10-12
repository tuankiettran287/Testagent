import io
import json
import os
import queue
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from testagent import api as api_module, db
from testagent.ai_providers import ProviderManager, parse_object
from testagent.cli_transport import CliError, CodexRpc, account_environment, executable, run_cli
from testagent.config import settings


def connected(provider='codex'):
    return {'id': provider, 'name': provider, 'installed': True, 'connected': True, 'account': None, 'plan': None,
            'models': [{'id': 'model-a', 'name': 'Model A', 'default': True}], 'message': None}


def native_accounts(manager):
    return patch.object(manager, '_native_status', side_effect=lambda p, *a, **kw: connected(p))


def effort_account(provider='codex', *args, **kwargs):
    state = connected(provider)
    if provider == 'codex':
        state['models'] = [
            {'id': 'model-a', 'name': 'Model A', 'default': True, 'default_effort': 'low',
             'efforts': [{'id': level, 'name': level} for level in ('low', 'high', 'ultra')]},
            {'id': 'model-b', 'name': 'Model B', 'default_effort': 'medium',
             'efforts': [{'id': 'medium', 'name': 'medium'}]},
        ]
    return state


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.manager = ProviderManager(Path(self.directory.name))

    def tearDown(self):
        self.manager.close()
        self.directory.cleanup()

    def test_selection_persists_and_rejects_model_from_other_provider(self):
        with native_accounts(self.manager), patch.object(self.manager, 'command', return_value=['cli']):
            self.manager.start_login('codex')
            selected = self.manager.select('codex', 'model-a')
            self.assertEqual(self.manager.read_selection(), selected)
            with self.assertRaises(ValueError):
                self.manager.select('codex', 'other-provider-model')
            self.assertEqual(self.manager.read_selection(), selected)

    def test_missing_or_partial_selection_does_not_fall_back(self):
        with self.assertRaises(CliError):
            self.manager.resolve()
        with self.assertRaises(ValueError):
            self.manager.resolve('codex', None)

    def test_expired_session_is_rejected(self):
        with native_accounts(self.manager), patch.object(self.manager, 'command', return_value=['cli']):
            self.manager.start_login('codex')
        with patch.object(self.manager, '_native_status', return_value={'connected': False, 'models': [], 'message': 'expired'}):
            with self.assertRaisesRegex(CliError, 'expired'):
                self.manager.resolve('codex', 'model-a')

    def test_codex_catalog_is_paginated_and_account_backed(self):
        rpc = Mock()
        rpc.login_outcomes = {}
        rpc.request.side_effect = [
            {'account': {'type': 'chatgpt', 'planType': 'plus'}},
            {'data': [{'model': 'first', 'displayName': 'First'}], 'nextCursor': 'next'},
            {'data': [{'model': 'second', 'displayName': 'Second'}, {'model': 'hidden', 'hidden': True}], 'nextCursor': None},
        ]
        with patch.object(self.manager, '_codex', return_value=rpc):
            result = self.manager._codex_status()
        self.assertEqual([row['id'] for row in result['models']], ['first', 'second'])
        self.assertEqual(rpc.request.call_args_list[2].args[1]['cursor'], 'next')

    def test_codex_api_key_account_is_not_connected(self):
        rpc = Mock()
        rpc.login_outcomes = {}
        rpc.request.return_value = {'account': {'type': 'apiKey'}}
        with patch.object(self.manager, '_codex', return_value=rpc):
            self.assertFalse(self.manager._codex_status()['connected'])
        self.assertEqual(rpc.request.call_count, 1)

    def test_codex_effort_capabilities_come_from_each_native_model(self):
        rpc = Mock()
        rpc.login_outcomes = {}
        rpc.request.side_effect = [
            {'account': {'type': 'chatgpt'}},
            {'data': [
                {'model': 'reasoning', 'defaultReasoningEffort': 'low',
                 'supportedReasoningEfforts': [{'reasoningEffort': 'low', 'description': 'Fast'}, {'reasoningEffort': 'high'}]},
                {'model': 'plain'},
            ]},
        ]
        with patch.object(self.manager, '_codex', return_value=rpc):
            models = self.manager._codex_status()['models']
        self.assertEqual(models[0]['default_effort'], 'low')
        self.assertEqual([e['id'] for e in models[0]['efforts']], ['low', 'high'])
        self.assertEqual(models[0]['efforts'][0]['description'], 'Fast')
        self.assertEqual(models[1]['efforts'], [])

    def test_effort_persists_across_restart_and_model_changes_use_new_default(self):
        with patch.object(self.manager, '_native_status', side_effect=effort_account), patch.object(self.manager, 'command', return_value=['cli']):
            self.manager.start_login('codex')
            self.assertEqual(self.manager.read_selection()['effort'], 'low')
            selected = self.manager.select('codex', 'model-a', 'ultra')
            restored = ProviderManager(Path(self.directory.name))
            try:
                with patch.object(restored, '_native_status', side_effect=effort_account), patch.object(restored, 'command', return_value=['cli']):
                    self.assertEqual(restored.overview()['selection'], selected)
            finally:
                restored.close()
            self.assertEqual(self.manager.select('codex', 'model-b')['effort'], 'medium')
            self.assertEqual(self.manager.select('codex', 'model-a')['effort'], 'low')

    def test_unsupported_effort_is_rejected_without_overwriting_selection(self):
        with patch.object(self.manager, '_native_status', side_effect=effort_account), patch.object(self.manager, 'command', return_value=['cli']):
            self.manager.start_login('codex')
            selected = self.manager.select('codex', 'model-a', 'high')
            for model, effort in [('model-a', 'invented'), ('model-b', 'ultra')]:
                with self.subTest(model=model), self.assertRaises(ValueError):
                    self.manager.select('codex', model, effort)
                self.assertEqual(self.manager.read_selection(), selected)
            self.manager.logout('codex')
            self.manager.start_login('antigravity')
            with self.assertRaises(ValueError):
                self.manager.select('antigravity', 'model-a', 'high')
            self.assertNotIn('effort', self.manager.read_selection())

    def test_removed_effort_capability_falls_back_to_current_model_default(self):
        with patch.object(self.manager, '_native_status', side_effect=effort_account), patch.object(self.manager, 'command', return_value=['cli']):
            self.manager.start_login('codex')
            self.manager.select('codex', 'model-a', 'ultra')
            updated = effort_account()
            updated['models'][0]['efforts'] = [{'id': 'low', 'name': 'low'}]
            with patch.object(self.manager, '_native_status', return_value=updated):
                self.assertEqual(self.manager.overview(refresh=True)['selection']['effort'], 'low')

    def test_codex_device_login_uses_native_oauth(self):
        rpc = Mock()
        rpc.request.return_value = {'loginId': 'login-1', 'verificationUrl': 'https://auth.openai.com/codex/device', 'userCode': 'ABCD'}
        with patch.object(self.manager, 'command', return_value=['codex']), patch.object(self.manager, '_codex', return_value=rpc), \
             patch.object(self.manager, '_native_status', return_value={'connected': False, 'models': []}):
            result = self.manager.start_login('codex', True)
            self.manager.cancel_login('codex')
        self.assertEqual(result['user_code'], 'ABCD')
        self.assertEqual(rpc.request.call_args_list[0].args, ('account/login/start', {'type': 'chatgptDeviceCode'}))
        self.assertEqual(rpc.request.call_args_list[1].args, ('account/login/cancel', {'loginId': 'login-1'}))

    def test_native_accounts_are_not_implicitly_connected(self):
        with native_accounts(self.manager) as native, patch.object(self.manager, 'command', return_value=['cli']):
            state = self.manager.overview(refresh=True)
        native.assert_not_called()
        self.assertFalse(state['ready'])
        self.assertEqual(sum(p['connected'] for p in state['providers']), 0)

    def test_only_one_provider_and_model_is_selected_on_connect(self):
        with native_accounts(self.manager), patch.object(self.manager, 'command', return_value=['cli']):
            self.assertEqual(self.manager.start_login('antigravity')['mode'], 'connected')
            state = self.manager.overview(refresh=True)
            self.assertTrue(state['ready'])
            self.assertEqual(state['selection'], {'provider': 'antigravity', 'model': 'model-a'})
            self.assertEqual([p['id'] for p in state['providers'] if p['connected']], ['antigravity'])
            for provider in ('codex', 'claude'):
                with self.assertRaises(CliError):
                    self.manager.start_login(provider)
                with self.assertRaises(CliError):
                    self.manager.select(provider, 'model-a')
                with self.assertRaises(CliError):
                    self.manager.resolve(provider, 'model-a')

    def test_antigravity_logout_persists_without_launching_cli_or_revoking_credentials(self):
        with native_accounts(self.manager), patch.object(self.manager, 'command', return_value=['cli']):
            self.manager.start_login('antigravity')
        with patch('testagent.ai_providers.subprocess.Popen') as launch, \
             patch('testagent.ai_providers.run_cli') as run, patch.object(self.manager, 'command') as command:
            self.manager.logout('antigravity')
        launch.assert_not_called()
        run.assert_not_called()
        command.assert_not_called()
        self.assertIsNone(self.manager.read_selection())
        restored = ProviderManager(Path(self.directory.name))
        try:
            with native_accounts(restored) as native, patch.object(restored, 'command', return_value=['cli']):
                for _ in range(2):
                    state = restored.overview(refresh=True)
                    self.assertFalse(state['ready'])
                    self.assertFalse(any(p['connected'] for p in state['providers']))
                native.assert_not_called()
                restored.start_login('codex')
                self.assertTrue(restored.overview()['ready'])
        finally:
            restored.close()

    def test_pending_login_blocks_others_and_cancel_releases_reservation(self):
        rpc = Mock()
        rpc.request.return_value = {'loginId': 'pending'}
        with patch.object(self.manager, 'command', return_value=['cli']), patch.object(self.manager, '_codex', return_value=rpc), \
             patch.object(self.manager, '_native_status', return_value={'connected': False, 'models': []}):
            self.manager.start_login('codex')
            self.assertEqual(self.manager.overview()['pending_provider'], 'codex')
            with self.assertRaises(CliError):
                self.manager.start_login('claude')
            self.manager.cancel_login('codex')
            self.assertIsNone(self.manager.session['pending_provider'])
        with native_accounts(self.manager), patch.object(self.manager, 'command', return_value=['cli']):
            self.manager.start_login('claude')
            self.assertTrue(self.manager.overview()['ready'])

    def test_concurrent_login_requests_cannot_connect_two_providers(self):
        def login(provider):
            try:
                self.manager.start_login(provider)
                return 'connected'
            except CliError:
                return 'blocked'
        with native_accounts(self.manager), patch.object(self.manager, 'command', return_value=['cli']), \
             ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(login, ('codex', 'antigravity', 'claude')))
            self.assertEqual(results.count('connected'), 1)
            self.assertEqual(sum(p['connected'] for p in self.manager.overview()['providers']), 1)

    def test_active_session_and_selected_model_survive_restart(self):
        with native_accounts(self.manager), patch.object(self.manager, 'command', return_value=['cli']):
            self.manager.start_login('codex')
        restored = ProviderManager(Path(self.directory.name))
        try:
            with native_accounts(restored), patch.object(restored, 'command', return_value=['cli']):
                state = restored.overview()
                self.assertEqual(state['active_provider'], 'codex')
                self.assertTrue(state['ready'])
                self.assertEqual(sum(p['connected'] for p in state['providers']), 1)
        finally:
            restored.close()

    def test_legacy_selection_migrates_only_its_provider(self):
        self.manager.session_file.unlink()
        self.manager.selection_file.write_text(json.dumps({'provider': 'codex', 'model': 'model-a'}), encoding='utf-8')
        restored = ProviderManager(Path(self.directory.name))
        try:
            with native_accounts(restored), patch.object(restored, 'command', return_value=['cli']):
                state = restored.overview()
                self.assertEqual([p['id'] for p in state['providers'] if p['connected']], ['codex'])
        finally:
            restored.close()

    def test_claude_api_key_auth_is_rejected(self):
        output = json.dumps({'loggedIn': True, 'authMethod': 'api_key', 'apiProvider': 'firstParty'})
        with patch('testagent.ai_providers.run_cli', return_value=(0, output, '')) as run:
            self.assertFalse(self.manager._claude_status(['claude'])['connected'])
        self.assertEqual(run.call_count, 1)

    def test_claude_catalog_comes_from_initialize_without_user_prompt(self):
        account = json.dumps({'loggedIn': True, 'authMethod': 'oauth', 'apiProvider': 'firstParty'})
        catalog = json.dumps({'type': 'control_response', 'response': {'subtype': 'success', 'request_id': 'catalog',
                              'response': {'models': [{'value': 'new-model', 'displayName': 'Native model'}]}}})
        with patch('testagent.ai_providers.run_cli', side_effect=[(0, account, ''), (0, catalog, '')]) as run:
            result = self.manager._claude_status(['claude'])
        self.assertEqual(result['models'][0]['id'], 'new-model')
        self.assertEqual(json.loads(run.call_args.kwargs['input_text'])['type'], 'control_request')

    def test_antigravity_catalog_handles_console_spinner_and_fails_closed(self):
        with patch.object(self.manager, '_check_antigravity_account_mode'), patch('testagent.ai_providers.run_cli', side_effect=[
            (0, 'Quota:\nGemini Models Weekly Limit Remaining 100%', ''),
            (0, '⠋ Fetching models...gemini-new-high     Gemini New (High)\nclaude-new-model    Claude New', ''),
        ]):
            result = self.manager._antigravity_status(['agy'])
        self.assertEqual([row['id'] for row in result['models']], ['gemini-new-high', 'claude-new-model'])
        with patch.object(self.manager, '_check_antigravity_account_mode'), patch('testagent.ai_providers.run_cli', return_value=(0, 'Login required', '')):
            self.assertFalse(self.manager._antigravity_status(['agy'])['connected'])

    def test_claude_only_exposes_effort_when_native_model_supports_it(self):
        account = json.dumps({'loggedIn': True, 'authMethod': 'oauth', 'apiProvider': 'firstParty'})
        catalog = json.dumps({'response': {'subtype': 'success', 'request_id': 'catalog', 'response': {'models': [
            {'value': 'opus', 'displayName': 'Opus', 'supportsEffort': True, 'supportedEffortLevels': ['low', 'max']},
            {'value': 'haiku', 'displayName': 'Haiku', 'supportsEffort': False, 'supportedEffortLevels': ['high']},
        ]}}})
        with patch('testagent.ai_providers.run_cli', side_effect=[(0, account, ''), (0, catalog, '')]):
            models = self.manager._claude_status(['claude'])['models']
        self.assertEqual([e['id'] for e in models[0]['efforts']], ['low', 'max'])
        self.assertEqual(models[1]['efforts'], [])

    def test_codex_generation_sends_effort_on_turn_start(self):
        rpc = Mock()
        rpc.request.side_effect = [{'thread': {'id': 'thread'}}, {'turn': {'id': 'turn'}}]
        rpc.receive.return_value = {'method': 'turn/completed', 'params': {'threadId': 'thread', 'turn': {
            'id': 'turn', 'status': 'completed', 'items': [{'type': 'agentMessage', 'id': 'answer', 'text': '{"ok":true}'}],
        }}}
        with patch('testagent.ai_providers.CodexRpc', return_value=rpc):
            self.assertEqual(self.manager._complete_codex('system', 'request', 'model-a', 'high'), {'ok': True})
        self.assertEqual(rpc.request.call_args_list[1].args[0], 'turn/start')
        self.assertEqual(rpc.request.call_args_list[1].args[1]['effort'], 'high')
        self.assertNotIn('effort', rpc.request.call_args_list[0].args[1])
        rpc.close.assert_called_once()

    def test_claude_generation_forwards_selected_effort_and_omits_it_when_default(self):
        for effort in ('max', None):
            with self.subTest(effort=effort):
                selection = {'provider': 'claude', 'model': 'opus'}
                if effort:
                    selection['effort'] = effort
                with patch.object(self.manager, 'resolve', return_value=selection), patch.object(self.manager, 'command', return_value=['claude']), \
                     patch('testagent.ai_providers.run_cli', return_value=(0, '{"result":"{\\"ok\\":true}"}', '')) as run:
                    self.assertEqual(self.manager.complete('system', 'request', 'claude', 'opus', effort), {'ok': True})
                args = run.call_args.args[0]
                if effort:
                    self.assertEqual(args[args.index('--effort') + 1], 'max')
                else:
                    self.assertNotIn('--effort', args)

    def test_claude_generation_uses_stdin_and_disables_tools(self):
        response = json.dumps({'result': '{"summary":"ok"}'})
        with patch.object(self.manager, 'resolve', return_value={'provider': 'claude', 'model': 'model-a'}), patch.object(self.manager, 'command', return_value=['claude']), patch('testagent.ai_providers.run_cli', return_value=(0, response, '')) as run:
            result = self.manager.complete('system', 'untrusted $() `prompt`', 'claude', 'model-a')
        self.assertEqual(result, {'summary': 'ok'})
        self.assertEqual(run.call_args.kwargs['input_text'], 'untrusted $() `prompt`')
        args = run.call_args.args[0]
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertEqual(args[args.index('--model') + 1], 'model-a')


class TransportTests(unittest.TestCase):
    def test_inherited_keys_and_endpoint_overrides_are_removed(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'secret', 'ANTHROPIC_API_KEY': 'secret', 'GEMINI_API_KEY': 'secret',
                                     'ANTHROPIC_BASE_URL': 'http://outside', 'CLAUDECODE': '1', 'PATH': 'retained'}, clear=True):
            self.assertEqual(account_environment(), {'PATH': 'retained'})

    def test_windows_npm_shim_is_launched_with_node_without_shell(self):
        with patch('testagent.cli_transport.shutil.which', side_effect=['C:/npm/codex.cmd', 'C:/node/node.exe']), patch.object(Path, 'is_file', return_value=True):
            result = executable('codex', '@openai/codex/bin/codex.js')
        self.assertEqual(result[0], 'C:/node/node.exe')
        self.assertTrue(result[1].replace('\\', '/').endswith('/node_modules/@openai/codex/bin/codex.js'))

    def test_invalid_and_non_object_json_is_rejected(self):
        self.assertEqual(parse_object('```json\n{"ok":true}\n```'), {'ok': True})
        for content in ('[]', 'null', 'not JSON', 'text {"ok":true}'):
            with self.subTest(content=content), self.assertRaises(CliError):
                parse_object(content)

    def test_timeout_stops_a_real_child_process(self):
        start = time.monotonic()
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(CliError):
            run_cli([sys.executable, '-c', 'import time; time.sleep(20)'], cwd=Path(directory), timeout=1)
        self.assertLess(time.monotonic() - start, 12)

    def test_rpc_preserves_events_arriving_before_request_response(self):
        rpc = CodexRpc.__new__(CodexRpc)
        from collections import deque
        rpc.pending_events = deque()
        rpc.login_outcomes = {}
        rpc.next_id = 0
        rpc.messages = queue.Queue()
        rpc.proc = Mock()
        rpc.proc.poll.return_value = None
        rpc.proc.stdin = io.StringIO()
        event = {'method': 'item/completed', 'params': {'item': {'text': 'answer'}}}
        rpc.messages.put(event)
        rpc.messages.put({'id': 1, 'result': {'turn': {'id': 'turn'}}})
        self.assertEqual(rpc.request('turn/start')['turn']['id'], 'turn')
        self.assertEqual(rpc.receive(1), event)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = replace(settings, data_dir=Path(self.directory.name))
        self.manager = ProviderManager(self.config.data_dir)
        self.patches = [patch.object(db, 'settings', self.config), patch.object(api_module, 'provider_manager', self.manager),
                        native_accounts(self.manager), patch.object(self.manager, 'command', return_value=['cli']),
                        patch.object(api_module, 'run_task')]
        for item in self.patches:
            item.start()
        self.client = TestClient(api_module.app)
        self.client.__enter__()
        self.project = self.client.post('/api/projects', json={'name': 'AI testing'}).json()['id']

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def test_task_pins_selected_provider_and_model_before_background_work(self):
        self.manager.start_login('codex')
        self.manager.select('codex', 'model-a')
        result = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'prompt': 'Generate a test case', 'function': 'gen_testcase'})
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.json()['ai_provider'], 'codex')
        self.assertEqual(result.json()['ai_model'], 'model-a')
        self.assertEqual(api_module.run_task.call_args.args[-3:], ('codex', 'model-a', None))
        self.manager.logout('codex')
        self.manager.start_login('antigravity')
        stored = self.client.get('/api/agent/tasks/' + result.json()['id']).json()
        self.assertEqual(stored['ai_provider'], 'codex')

    def test_unconfigured_task_does_not_create_database_row(self):
        result = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'prompt': 'Generate a test case'})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(db.many('SELECT * FROM tasks'), [])
        api_module.run_task.assert_not_called()

    def test_task_snapshots_effort_and_rejects_unsupported_values(self):
        with patch.object(self.manager, '_native_status', side_effect=effort_account):
            self.manager.start_login('codex')
            selection = {'provider': 'codex', 'model': 'model-a', 'effort': 'high'}
            response = self.client.put('/api/ai/selection', json=selection)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), selection)
            payload = {'project_id': self.project, 'prompt': 'Generate a test case', 'function': 'gen_testcase'}
            result = self.client.post('/api/agent/tasks', json=payload)
            self.assertEqual(result.status_code, 202)
            self.assertEqual(result.json()['ai_effort'], 'high')
            self.assertEqual(api_module.run_task.call_args.args[-3:], ('codex', 'model-a', 'high'))
            self.manager.select('codex', 'model-a', 'low')
            self.assertEqual(self.client.get('/api/agent/tasks/' + result.json()['id']).json()['ai_effort'], 'high')
            self.assertEqual(self.client.post('/api/agent/tasks', json={**payload, 'effort': 'max'}).status_code, 422)
            self.assertEqual(len(db.many('SELECT * FROM tasks')), 1)
            self.assertEqual(self.client.put('/api/ai/selection', json={**selection, 'effort': 'unsupported'}).status_code, 422)
            self.assertEqual(self.manager.read_selection()['effort'], 'low')

    def test_unknown_provider_model_and_partial_pair_are_rejected(self):
        self.manager.start_login('codex')
        for selection in ({'provider': 'unknown', 'model': 'model-a'}, {'provider': 'codex', 'model': 'unknown-model'}):
            self.assertEqual(self.client.put('/api/ai/selection', json=selection).status_code, 422)
        result = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'prompt': 'Generate a test case', 'provider': 'codex'})
        self.assertEqual(result.status_code, 422)

    def test_login_select_and_task_api_cannot_bypass_single_provider(self):
        self.assertEqual(self.client.post('/api/ai/providers/antigravity/login', json={}).status_code, 200)
        self.assertTrue(self.client.get('/api/health').json()['model_configured'])
        self.assertEqual(self.client.post('/api/ai/providers/codex/login', json={}).status_code, 409)
        self.assertEqual(self.client.put('/api/ai/selection', json={'provider': 'codex', 'model': 'model-a'}).status_code, 409)
        result = self.client.post('/api/agent/tasks', json={'project_id': self.project, 'prompt': 'Generate a test case',
                                  'provider': 'codex', 'model': 'model-a'})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(db.many('SELECT * FROM tasks'), [])
        api_module.run_task.assert_not_called()
        self.assertEqual(self.client.post('/api/ai/providers/antigravity/logout', json={}).status_code, 200)
        self.assertFalse(self.client.get('/api/health').json()['model_configured'])
        self.assertFalse(any(p['connected'] for p in self.client.get('/api/ai/providers?refresh=true').json()['providers']))
        self.assertEqual(self.client.post('/api/ai/providers/codex/login', json={}).status_code, 200)

    def test_unrelated_browser_origin_cannot_change_cli_account(self):
        with patch.object(self.manager, 'logout') as logout:
            result = self.client.post('/api/ai/providers/codex/logout', headers={'Origin': 'https://unrelated.example'})
        self.assertEqual(result.status_code, 403)
        logout.assert_not_called()


if __name__ == '__main__':
    unittest.main()
