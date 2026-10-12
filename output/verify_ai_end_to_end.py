"""Run real AI against a temporary database, never modifying user projects."""
import json
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from testagent import api as api_module, db, llm
from testagent.ai_providers import ProviderManager
from testagent.config import settings


with tempfile.TemporaryDirectory(prefix='testagent-e2e-') as directory:
    config = replace(settings, data_dir=Path(directory))
    manager = ProviderManager(config.data_dir)
    with patch.object(db, 'settings', config), patch.object(api_module, 'provider_manager', manager), patch.object(llm, 'provider_manager', manager):
        with TestClient(api_module.app) as client:
            project = client.post('/api/projects', json={'name': 'CLI integration verification'}).json()['id']
            content = 'Login accepts an email and password. Empty email shows a validation error. Correct email and password redirect to the dashboard. Invalid password shows an error.'
            uploaded = client.post(f'/api/projects/{project}/documents', files={'file': ('login.txt', content, 'text/plain')})
            assert uploaded.status_code == 201, uploaded.text
            for provider, model, skill, prompt in [
                ('codex', 'gpt-6.1-sol', 'gen_testcase', 'Generate exactly one manual test case for the empty email login requirement. Use Vietnamese.'),
                ('antigravity', 'gemini-3.8-flash-low', 'requirement_under', 'Analyze the supplied login requirements. Give a concise Vietnamese summary and one finding.'),
            ]:
                login = client.post(f'/api/ai/providers/{provider}/login', json={})
                assert login.status_code == 200 and login.json()['mode'] == 'connected', login.text
                result = client.post('/api/agent/tasks', json={'project_id': project, 'prompt': prompt, 'function': skill, 'provider': provider, 'model': model})
                assert result.status_code == 202, result.text
                task = client.get('/api/agent/tasks/' + result.json()['id']).json()
                assert task['status'] == 'COMPLETED', task['error']
                assert task['ai_provider'] == provider and task['ai_model'] == model
                output = json.loads(task['summary'])
                assert output['summary']
                print(json.dumps({'provider': provider, 'model': model, 'status': task['status'], 'kind': output['kind'], 'case_count': output.get('case_count')}, ensure_ascii=False))
                assert client.post(f'/api/ai/providers/{provider}/logout', json={}).status_code == 200
            cases = client.get(f'/api/projects/{project}/tests').json()
            assert len(cases) == 1, len(cases)
            assert cases[0]['source_ids'] == [uploaded.json()['source_id']], cases[0]['source_ids']
            print('Verified source attribution, model snapshot, test generation, and requirement analysis.')
