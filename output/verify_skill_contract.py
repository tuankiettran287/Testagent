"""Exercise updated role prompts with native CLI inference and a local fixture.

Keeps the main application database untouched. Artifacts remain under output/.
"""
import json
import re
import sys
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from testagent import db, planner, runner
from testagent.ai_providers import provider_manager
from testagent.config import settings


class LoginFixture(BaseHTTPRequestHandler):
    def do_GET(self):
        content = b'''<!doctype html><html><head><title>Native skill verification</title></head><body>
        <p>Authorized public test fixture: native_demo / portable_test_secret_42</p>
        <main id="app"><h1>Portal login</h1><form id="signin">
        <label>Account name <input data-qa="account-id" autocomplete="username"></label>
        <label>Passphrase <input data-qa="passphrase" type="password" autocomplete="current-password"></label>
        <button data-qa="enter-portal" type="submit">Enter portal</button></form>
        <div role="alert" data-qa="signin-problem"></div></main>
        <script>
        const portal = () => {
          document.querySelector('#app').innerHTML = '<h1 data-qa="portal-heading">Portal for native_demo</h1>';
          history.replaceState({}, '', '/portal');
        };
        document.querySelector('#signin').addEventListener('submit', event => {
          event.preventDefault();
          const account = document.querySelector('[data-qa="account-id"]').value;
          const passphrase = document.querySelector('[data-qa="passphrase"]').value;
          if (account === 'native_demo' && passphrase === 'portable_test_secret_42') {
            localStorage.setItem('authenticated', 'yes'); portal();
          } else { document.querySelector('[data-qa="signin-problem"]').textContent = 'The passphrase is incorrect.'; }
        });
        if (localStorage.getItem('authenticated')) portal();
        </script></body></html>'''
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    selection = provider_manager.resolve()
    directory = ROOT / 'output' / 'skill-contract-verification' / db.uid()
    directory.mkdir(parents=True)
    config = replace(settings, data_dir=directory)
    website = ThreadingHTTPServer(('127.0.0.1', 0), LoginFixture)
    thread = threading.Thread(target=website.serve_forever, daemon=True)
    thread.start()
    base_url = f'http://127.0.0.1:{website.server_port}/signin'
    calls = []
    native_complete = planner.complete_json

    def complete(system, request, provider, model, effort):
        assert (provider, model, effort) == (selection['provider'], selection['model'], selection['effort'])
        context = json.loads(request)
        files = re.findall(r'<!-- instruction file: ([^>]+) -->', system)
        phase = 'exploration' if 'observation' in context else 'final'
        assert 'automation-core.md' in files
        assert ('automation-patterns.md' in files) == (phase == 'final' and context['function'] == 'ui_automation')
        result = native_complete(system, request, provider, model, effort)
        calls.append({'function': context['function'], 'phase': phase, 'files': files, 'result': result})
        print(json.dumps({'call': len(calls), 'function': context['function'], 'phase': phase,
                          'reset': result.get('reset_browser'), 'done': result.get('done'),
                          'summary': result.get('summary', '')[:150]}, ensure_ascii=False), flush=True)
        return result

    def task(project_id, function, prompt, **options):
        task_id = db.uid()
        db.execute("INSERT INTO tasks (id, project_id, prompt, intent, skill_file, status, created_at, ai_provider, ai_model, ai_effort) VALUES (?, ?, ?, ?, ?, 'QUEUED', ?, ?, ?, ?)",
                   (task_id, project_id, prompt, function, planner.get_skill(function).file, db.now(),
                    selection['provider'], selection['model'], selection['effort']))
        planner.run_task(task_id, project_id, prompt, function, provider=selection['provider'],
                         model=selection['model'], effort=selection['effort'], **options)
        item = db.one('SELECT * FROM tasks WHERE id=?', (task_id,))
        item['summary'] = json.loads(item['summary']) if item['summary'] else None
        print(json.dumps({'task': function, 'status': item['status'], 'error': item['error']}, ensure_ascii=False), flush=True)
        return item

    try:
        with patch.object(db, 'settings', config), patch.object(runner, 'settings', config), patch.object(planner, 'complete_json', side_effect=complete):
            db.init_db()
            project_id = db.uid()
            db.execute('INSERT INTO projects VALUES (?, ?, ?, ?, ?)',
                       (project_id, 'Isolated native skill fixture', base_url, 'local', db.now()))
            generated = task(project_id, 'ui_automation',
                'Tao dung hai test case doc lap cho website fixture: (1) dang nhap bang tai khoan native_demo, '
                'passphrase portable_test_secret_42, phai toi /portal va hien Portal for native_demo; '
                '(2) native_demo voi passphrase wrong_for_native_fixture phai bi tu choi, '
                'hien The passphrase is incorrect. va van o /signin. Day la cac quy tac da xac dinh. '
                'Kham pha tung kich ban tren browser sach, bao gom thao tac dang nhap trong moi test. '
                'Chi tao automation de xem lai, chua chay xac nhan.', execution_mode='generate')
            assert generated['status'] == 'READY', generated
            case_ids = generated['summary']['case_ids']
            assert len(case_ids) == 2 and set(generated['summary']['executable_ids']) == set(case_ids), generated
            cases = [db.decode_case(row) for row in db.many('SELECT * FROM test_cases')]
            for case in cases:
                payload = json.dumps(case['automation'])
                assert 'example_account' not in payload and 'example_password' not in payload, case
                assert case['source_ids'] == []
                actions = case['automation']['actions']
                assert actions[0]['action'] == 'navigate'
                assert any(action['action'] == 'fill' and action['value'] == 'native_demo' for action in actions)
                assert any(action['action'] == 'click' for action in actions)
                assert any(action['action'] == 'assert_text' for action in actions)
            assert not db.many('SELECT * FROM runs')
            reviewed = task(project_id, 'case_review',
                'Ra soat hai case da chon: oracle phai phu hop muc tieu, setup dang nhap phai doc lap, '
                'locator dung attribute quan sat. Chi ra gap co bang chung; chua co ket qua replay, '
                'khong ket luan PASS. Khong doi ky vong.', case_ids=case_ids)
            assert reviewed['status'] == 'COMPLETED', reviewed
            before = len(calls)
            executed = task(project_id, 'run_tests', 'Chay hai case doc lap song song.',
                            case_ids=case_ids, run_mode='parallel', workers=2)
            assert len(calls) == before, 'Deterministic execution called AI'
            assert executed['status'] == 'COMPLETED', executed
            run_id = executed['summary']['run_id']
            run = db.one('SELECT * FROM runs WHERE id=?', (run_id,))
            run['summary'] = json.loads(run['summary'])
            assert run['summary']['counts']['PASS'] == 2 and run['summary']['completed'] == 2, run
            results = db.many('SELECT * FROM run_results WHERE run_id=?', (run_id,))
            for result in results:
                result['artifacts'] = json.loads(result['artifacts'])
                assert any(name.endswith('.spec.ts') for name in result['artifacts']), result
                assert any(name.endswith('-trace.zip') for name in result['artifacts']), result
            record = {'selection': selection, 'generated': generated, 'cases': cases, 'review': reviewed,
                      'run': run, 'results': results, 'native_calls': calls, 'sources': db.many('SELECT * FROM sources')}
            (directory / 'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'verified': True, 'parallel_PASS': 2, 'native_calls': len(calls),
                              'record': str(directory / 'verification.json')}), flush=True)
    finally:
        provider_manager.close()
        website.shutdown()
        website.server_close()
        thread.join(timeout=3)


if __name__ == '__main__':
    main()
