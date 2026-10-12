"""Verify real URL-only AI generation and browser execution in a temporary project."""
import json
import tempfile
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from testagent import api as api_module, db, llm, runner
from testagent.ai_providers import ProviderManager
from testagent.config import settings


class DemoWebsite(BaseHTTPRequestHandler):
    def do_GET(self):
        page = b'''<!doctype html><html><head><title>Source-free demo</title></head>
        <body><h1>Sign in</h1><form><label for="email">Email</label>
        <input id="email" type="email" required><label for="password">Password</label>
        <input id="password" type="password" required><button id="login" type="submit">Log in</button>
        </form></body></html>'''
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, *args):
        pass


website = ThreadingHTTPServer(('127.0.0.1', 0), DemoWebsite)
thread = threading.Thread(target=website.serve_forever, daemon=True)
thread.start()
try:
    with tempfile.TemporaryDirectory(prefix='testagent-optional-e2e-') as directory:
        config = replace(settings, data_dir=Path(directory))
        manager = ProviderManager(config.data_dir)
        try:
            login = manager.start_login('codex')
            assert login['mode'] == 'connected', 'Codex account must already be logged in for this verification'
            with patch.object(db, 'settings', config), patch.object(api_module, 'provider_manager', manager), \
                 patch.object(llm, 'provider_manager', manager), patch.object(runner, 'settings', config):
                with TestClient(api_module.app) as client:
                    base_url = f'http://127.0.0.1:{website.server_port}/login'
                    project = client.post('/api/projects', json={'name': 'URL-only verification', 'base_url': base_url, 'environment': 'local'}).json()['id']
                    assert client.get(f'/api/projects/{project}/sources').json() == []
                    current = manager.read_selection()
                    models = manager.status('codex')['models']
                    model = next(row for row in models if row['id'] == current['model'])
                    assert any(row['id'] == 'low' for row in model['efforts'])
                    selection = manager.select('codex', current['model'], 'low')
                    result = client.post('/api/agent/tasks', json={
                        'project_id': project, 'function': 'ui_automation', **selection,
                        'prompt': 'Tạo đúng một UI smoke test có automation cho trang ở Base URL. Mở trang và chỉ assert_visible cho các control quan sát được: Email, Password và Log in. Không click, không submit, không nhập dữ liệu. Không có tài liệu, SRS hay repository; dùng quan sát trang thực tế và viết mô tả tiếng Việt.',
                    })
                    assert result.status_code == 202, result.text
                    task = client.get('/api/agent/tasks/' + result.json()['id']).json()
                    assert task['status'] == 'COMPLETED', task['error']
                    assert task['ai_effort'] == 'low', task
                    cases = client.get(f'/api/projects/{project}/tests').json()
                    assert len(cases) == 1 and cases[0]['automation'], cases
                    assert cases[0]['source_ids'] == [], cases[0]['source_ids']
                    assert client.get(f'/api/projects/{project}/sources').json() == []
                    assert all(action['action'] in {'navigate', 'assert_visible'} for action in cases[0]['automation']['actions'])
                    output = json.loads(task['summary'])
                    assert output['workflow'] == 'ui_automation' and output['run_id']
                    run = client.get('/api/runs/' + output['run_id']).json()
                    assert run['status'] == 'COMPLETED', run
                    assert run['results'][0]['status'] == 'PASS', run
                    print(json.dumps({'provider': selection['provider'], 'model': selection['model'], 'effort': task['ai_effort'],
                                      'sources': 0, 'task': task['status'], 'cases': len(cases),
                                      'browser_test': run['results'][0]['status']}, ensure_ascii=False), flush=True)
        finally:
            manager.close()
finally:
    website.shutdown()
    website.server_close()
    thread.join(timeout=3)
