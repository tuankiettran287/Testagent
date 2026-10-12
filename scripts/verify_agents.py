"""Exercise every registered role and analysis helper on an isolated local app.

Default mode uses deterministic model responses and real HTTP/Chromium execution.
--live uses the application's selected provider/model/effort for every AI call.
The report distinguishes model mode, fixture evidence and actual executions.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from contextlib import ExitStack
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from testagent import db, planner, runner
from testagent.browser_bridge import browser_runner_available
from testagent.config import settings
from testagent.knowledge import add_source
from testagent.llm import complete_json
from testagent.orchestrator import RoutedSubTask, RoutedTask
from testagent.skills import SKILLS, get_skill


class FixturePage(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            content, kind = b'{"status":"healthy"}', 'application/json'
        elif self.path == '/':
            content = b'''<!doctype html><html><head><title>Status portal</title></head>
<body><h1>Status portal</h1><button onclick="document.getElementById('status').textContent='Healthy'">
Refresh status</button><p id="status">Not checked</p></body></html>'''
            kind = 'text/html; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *_):
        pass


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class AgentChecks:
    """A disposable database and real local target, reusable by unittest."""
    def __init__(self, *, live=False, selection=None):
        self.live = live
        self.selection = selection or {'provider': 'codex', 'model': 'fixture-model', 'effort': 'high'}
        self.calls = []
        self.call_lock = threading.Lock()
        self.stack = ExitStack()

    def __enter__(self):
        try:
            require(browser_runner_available(), 'Build browser_runner and install Chromium before verification')
            directory = self.stack.enter_context(tempfile.TemporaryDirectory(prefix='testagent-checks-'))
            config = replace(settings, data_dir=Path(directory))
            self.stack.enter_context(patch.object(db, 'settings', config))
            self.stack.enter_context(patch.object(runner, 'settings', config))
            self.stack.enter_context(patch.object(planner, 'complete_json', side_effect=self.complete))
            if os.getenv('TESTAGENT_EVIDENCE_DIR'):
                def export_evidence():
                    # Only this synthetic, credential-free status portal is exported.
                    if not hasattr(self, 'project_id'):
                        return
                    destination = Path(os.environ['TESTAGENT_EVIDENCE_DIR']) / self.project_id
                    destination.mkdir(parents=True, exist_ok=True)
                    artifacts = config.data_dir / 'artifacts'
                    if artifacts.is_dir():
                        shutil.copytree(artifacts, destination / 'artifacts', dirs_exist_ok=True)
                    report = {'project_id': self.project_id, 'synthetic_target': True,
                              'cases': db.many('SELECT id, level, automation IS NOT NULL AS browser_case FROM test_cases WHERE project_id=?', (self.project_id,)),
                              'runs': db.many('SELECT * FROM runs WHERE project_id=?', (self.project_id,)),
                              'results': db.many('SELECT rr.* FROM run_results rr JOIN runs r ON r.id=rr.run_id WHERE r.project_id=?', (self.project_id,))}
                    (destination / 'runs.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
                self.stack.callback(export_evidence)
            self.server = ThreadingHTTPServer(('127.0.0.1', 0), FixturePage)
            self.server.daemon_threads = True
            thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            thread.start()
            def close_server():
                self.server.shutdown()
                self.server.server_close()
                thread.join(5)
            self.stack.callback(close_server)
            db.init_db()
            self.project_id = db.uid()
            self.project = {'name': 'Isolated status portal', 'base_url': f'http://127.0.0.1:{self.server.server_port}',
                            'environment': 'local'}
            db.execute('INSERT INTO projects (id,name,base_url,environment,created_at) VALUES (?,?,?,?,?)',
                       (self.project_id, *self.project.values(), db.now()))
            self.source_id = add_source(self.project_id, 'document', 'Portal requirements', 'fixture:requirements',
                'The root page shows Status portal. Clicking Refresh status changes the status text from '
                'Not checked to Healthy. GET /health returns HTTP 200 with JSON {"status":"healthy"}. '
                'There is no login. Proposed capacity: 2000 concurrent users; latency thresholds are unknown.')
            add_source(self.project_id, 'code', 'discount.py', 'fixture:code',
                'def discount(total):\n    if total < 0:\n        raise ValueError("negative total")\n'
                '    return round(total * 0.9, 2)\n# Change: negative totals now raise ValueError.\n')
            self.api_case = self.insert_case('Health returns 200', 'api',
                api_request={'method': 'GET', 'path': '/health', 'expected_status': 200})
            self.manual_case = self.insert_case('Refresh displays Healthy', 'ui')
            self.failed_case = self.insert_case('Refresh displays Healthy with a stale locator', 'ui',
                automation=self.automation(stale=True))
            # This is a real failed browser execution, not an invented run record.
            self.failed_run = runner.prepare_run(self.project_id, [self.failed_case])
            runner.execute_run(self.failed_run)
            require(db.one('SELECT status FROM runs WHERE id=?', (self.failed_run,))['status'] == 'FAILED',
                    'The stale locator fixture must fail before repair')
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *args):
        self.stack.close()

    @staticmethod
    def automation(*, stale=False):
        return {'actions': [{'action': 'navigate', 'url': '/'},
                            {'action': 'click', 'target': {'role': 'button', 'name': 'Refresh status'}},
                            {'action': 'assert_text', 'target': {'id': 'obsolete-status' if stale else 'status'},
                             'value': 'Healthy'}]}

    def insert_case(self, title, level, **payload):
        case_id = db.uid()
        is_api = level == 'api'
        db.execute('''INSERT INTO test_cases
            (id,project_id,title,level,type,priority,preconditions,steps,expected,source_ids,automation,api_request,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (case_id, self.project_id, title, level, 'positive', 'high', '[]',
             json.dumps(['Request /health'] if is_api else ['Open /', 'Click Refresh status']),
             json.dumps(['HTTP 200'] if is_api else ['Status text contains Healthy']),
             json.dumps([self.source_id]), json.dumps(payload['automation']) if 'automation' in payload else None,
             json.dumps(payload['api_request']) if 'api_request' in payload else None, db.now()))
        return case_id

    def complete(self, system, user, provider=None, model=None, effort=None):
        request = json.loads(user)
        with self.call_lock:
            self.calls.append({'function': request['function'], 'browser_decision': 'observation' in request,
                               'sub_agent': 'delegation' in request.get('evidence', {})})
        require((provider, model, effort) == (self.selection['provider'], self.selection['model'], self.selection.get('effort')),
                'Provider/model/effort changed during execution')
        if self.live:
            return complete_json(system, user, provider, model, effort)
        function = request['function']
        if function == 'orchestrator':
            return {'function': 'performance', 'reason': 'The user requested a workload assessment.', 'sub_tasks': []}
        if 'observation' in request:
            if any(action['action'] == 'click' for action in request['current_session_actions']):
                return {'summary': 'Observed Healthy after refreshing status.', 'done': True}
            return {'summary': 'Refresh the status and verify Healthy.', 'scenarios': ['Refresh displays Healthy'],
                    'actions': self.automation()['actions'][1:]}
        evidence = request['evidence']
        skill = get_skill(function)
        if skill.mode == 'analysis':
            ids = [source['source_id'] for source in evidence.get('sources', [])]
            ids += [case['id'] for case in evidence.get('test_cases', [])]
            ids += [row['id'] for row in evidence.get('run', {}).get('results', [])]
            return {'summary': f'Focused {function} analysis from the supplied portal evidence.',
                    'findings': [{'title': 'Evidence and scope', 'detail': 'The stated portal behavior is supplied; '
                                  'capacity thresholds remain unknown.', 'evidence_ids': ids[:1] + ['fabricated']}],
                    'recommendations': ['Confirm the missing acceptance thresholds.']}
        case = {'title': 'Refresh displays Healthy', 'level': 'ui', 'type': 'positive', 'priority': 'high',
                'steps': ['Open /', 'Click Refresh status'], 'expected': ['Status text contains Healthy'],
                'source_ids': [self.source_id, 'fabricated']}
        intent = 'test_generation'
        if skill.workflow == 'browser':
            intent = 'ui_automation'
            case['automation'] = self.automation()
            originals = evidence.get('test_cases', [])
            if originals:
                case['origin_case_id'] = originals[0]['id']
        elif function == 'api_test':
            intent = 'api_testing'
            case.update(title='Health returns 200', level='api', steps=['Request /health'], expected=['HTTP 200'],
                        api_request={'method': 'GET', 'path': '/health', 'expected_status': 200})
        elif function == 'unit_test':
            intent = 'unit_testing'
            case.update(title='Discount rejects negative totals', level='unit', steps=['Call discount(-1)'],
                        expected=['ValueError is raised'],
                        unit_test_code='import pytest\nfrom discount import discount\ndef test_negative():\n'
                                       '    with pytest.raises(ValueError):\n        discount(-1)\n')
        return {'intent': intent, 'summary': 'One focused case based on supplied requirements.', 'cases': [case]}

    def new_task(self, skill_id, prompt):
        skill = get_skill(skill_id)
        task_id = db.uid()
        db.execute('''INSERT INTO tasks
            (id,project_id,prompt,intent,skill_file,status,created_at,ai_provider,ai_model,ai_effort)
            VALUES (?,?,?,?,?,'CREATED',?,?,?,?)''',
            (task_id, self.project_id, prompt, skill_id, skill.file, db.now(),
             self.selection['provider'], self.selection['model'], self.selection.get('effort')))
        return task_id

    def check_role(self, skill_id):
        skill = get_skill(skill_id)
        prompt = ('Dùng dữ liệu status portal đã cung cấp để thực hiện đúng phần việc bên dưới. '
                  'Giữ câu trả lời ngắn, tối đa một case hoặc hai findings. ')
        specific = {
            'orchestrator': 'Đề xuất workload hiệu năng cho /health với 2000 người dùng đồng thời; chỉ phân tích.',
            'unit_test': 'Sinh một unit test cho discount(-1) phải raise ValueError từ code đã cung cấp.',
            'gen_testcase': 'Thiết kế một test case cho thao tác Refresh status.',
            'ui_automation': 'Tạo và chạy đúng một browser case: mở /, nhấn Refresh status, kiểm tra status chứa Healthy.',
            'api_test': 'Sinh một API case GET /health, expected_status=200 theo yêu cầu đã xác nhận.',
            'automation_builder': 'Bổ sung browser automation cho đúng selected case; giữ nguyên kỳ vọng.',
            'repair_automation': 'Sửa locator obsolete-status trong browser case lỗi, giữ nguyên assert_text Healthy.',
            'repo_under': 'Đọc code discount.py và nêu kiến trúc/rủi ro được chứng minh.',
            'regression': 'Đánh giá regression cho thay đổi discount: total âm nay raise ValueError.',
            'report': 'Viết report dựa trên đúng run lỗi đã chọn, phân biệt fixture với sản phẩm thật.',
            'defect_analysis': 'Phân tích run lỗi: xác định lỗi locator từ bằng chứng, không bịa nội dung trace.',
            'run_tests': 'Chạy lại API case đã chọn.',
        }
        prompt += specific.get(skill_id, f'Thực hiện phần việc {skill_id} phù hợp với phạm vi đã cung cấp.')
        task_id = self.new_task(skill_id, prompt)
        options = {'execution_mode': 'run', **self.selection}
        if skill.requires == 'cases':
            options['case_ids'] = [self.api_case if skill_id == 'run_tests' else self.manual_case]
        if skill.requires == 'run':
            options['run_id'] = self.failed_run
        start, calls_before = time.monotonic(), len(self.calls)
        planner.run_task(task_id, self.project_id, prompt, skill_id, **options, agent_mode='single')
        task = db.one('SELECT * FROM tasks WHERE id=?', (task_id,))
        require(task['status'] == 'COMPLETED', f'{skill_id}: {task["status"]}: {task["error"]}: {task["summary"][:500]}')
        output = json.loads(task['summary'])
        if skill.workflow == 'browser' or skill.mode == 'execution':
            require(output['execution']['status'] == 'COMPLETED', f'{skill_id}: final execution failed')
            require(output['execution']['counts']['PASS'] >= 1, f'{skill_id}: no passing real execution')
        if skill.mode == 'analysis':
            require(all('fabricated' not in finding['evidence_ids'] for finding in output['findings']),
                    f'{skill_id}: invalid evidence survived validation')
        if skill.requires == 'cases' and skill.mode != 'execution':
            require(output.get('case_ids', [self.manual_case]) == [self.manual_case], 'Selected case identity changed')
        if skill.mode == 'execution':
            require(len(self.calls) == calls_before, 'Deterministic execution called AI')
        extra_execution = None
        if skill_id == 'api_test':
            require(bool(output['executable_ids']), 'API role produced no executable request from a known contract')
            execution_id = runner.prepare_run(self.project_id, output['executable_ids'])
            runner.execute_run(execution_id)
            extra_execution = db.one('SELECT status FROM runs WHERE id=?', (execution_id,))['status']
            require(extra_execution == 'COMPLETED', 'Generated API request did not pass against the real fixture')
        if skill_id == 'unit_test':
            cases = db.many('SELECT unit_test_code FROM test_cases WHERE task_id=?', (task_id,))
            require(bool(cases) and all(case['unit_test_code'] for case in cases), 'Unit role produced no reviewable code')
            for case in cases:
                ast.parse(case['unit_test_code'])
        return {'kind': 'skill', 'function': skill_id, 'status': 'PASS',
                'duration_ms': round((time.monotonic() - start) * 1000),
                'model_calls': len(self.calls) - calls_before, 'task_status': task['status'],
                'instruction_files': output.get('skills', [skill.file]),
                'generated_api_execution': extra_execution,
                'unit_code_validation': 'parsed; generated code is not executed' if skill_id == 'unit_test' else None}

    def check_helpers(self, helper_ids):
        lead_id = 'exploratory' if 'test_plan' in helper_ids else 'test_plan'
        prompt = 'Tổng hợp phân tích status portal từ các chuyên gia, tối đa hai findings; không chạy test mới.'
        task_id = self.new_task('orchestrator', prompt)
        plans = [RoutedSubTask(get_skill(skill_id),
                 f'Phân tích độc lập phần {skill_id} từ bằng chứng đã cung cấp, tối đa hai findings; không thao tác app.',
                 self.failed_run if get_skill(skill_id).requires == 'run' else None,
                 [self.manual_case] if get_skill(skill_id).requires == 'cases' else []) for skill_id in helper_ids]
        route = RoutedTask(get_skill(lead_id), 'Explicit verification of registered analysis helpers.', None, [], plans)
        before_cases = len(db.many('SELECT id FROM test_cases'))
        before_runs = len(db.many('SELECT id FROM runs'))
        # The helper plan is fixed for exhaustive coverage; only the separate
        # orchestrator role check tests actual model-selected routing.
        with patch.object(planner, 'AgentOrchestrator') as factory:
            factory.return_value.route.return_value = route
            planner.run_task(task_id, self.project_id, prompt, 'orchestrator', **self.selection, execution_mode='generate')
        parent = db.one('SELECT * FROM tasks WHERE id=?', (task_id,))
        children = db.many('SELECT * FROM tasks WHERE parent_task_id=?', (task_id,))
        require(parent['status'] == 'COMPLETED', f'Helper group failed: {parent["error"]}: {parent["summary"][:500]}')
        require(len(children) == len(helper_ids), 'Helper count mismatch')
        require(len(db.many('SELECT id FROM test_cases')) == before_cases and len(db.many('SELECT id FROM runs')) == before_runs,
                'An analysis helper changed cases or executed a run')
        checks = []
        for child in sorted(children, key=lambda child: helper_ids.index(child['intent'])):
            require(child['status'] == 'COMPLETED', f'Helper {child["intent"]} did not complete')
            output = json.loads(child['summary'])
            require('subagent-handoff.md' in output['skills'], 'Helper contract was not loaded')
            require(not db.many('SELECT id FROM tasks WHERE parent_task_id=?', (child['id'],)), 'Recursive delegation occurred')
            require(child['ai_provider'] == self.selection['provider'] and child['ai_model'] == self.selection['model']
                    and child['ai_effort'] == self.selection.get('effort'), 'Helper changed AI selection')
            checks.append({'kind': 'sub_agent', 'function': child['intent'], 'status': 'PASS',
                           'duration_ms': output['duration_ms'], 'instruction_files': output['skills'],
                           'group_metrics': json.loads(parent['orchestration'])['metrics']})
        return checks


def main():
    # Windows terminals may default to cp1252, while model errors use Vietnamese.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Use the currently connected AI account')
    parser.add_argument('--output', type=Path, help='JSON report destination')
    parser.add_argument('--skills', nargs='+', choices=[skill.id for skill in SKILLS], help='Check only the named lead roles')
    parser.add_argument('--skip-helpers', action='store_true', help='Skip analysis-helper groups for a focused retry')
    args = parser.parse_args()
    report = {'started_at': db.now(), 'model_mode': 'live' if args.live else 'mock', 'synthetic_target': True,
              'browser_and_http_execution': 'real', 'checks': [], 'errors': []}
    destination = args.output or Path('output') / ('agents-live-result.json' if args.live else 'agents-check-result.json')
    def save():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    selection = None
    try:
        if args.live:
            from testagent.ai_providers import provider_manager
            selection = provider_manager.resolve()
            report['selection'] = selection
        with AgentChecks(live=args.live, selection=selection) as checks:
            for skill in SKILLS:
                if args.skills is not None and skill.id not in args.skills:
                    continue
                print(f'Checking skill: {skill.id}', flush=True)
                try:
                    result = checks.check_role(skill.id)
                    report['checks'].append(result)
                    print(f'PASS {skill.id}: {result["duration_ms"]} ms', flush=True)
                except Exception as exc:
                    report['checks'].append({'kind': 'skill', 'function': skill.id, 'status': 'FAIL', 'error': str(exc)[:1500]})
                    print(f'FAIL {skill.id}: {str(exc)[:500]}', flush=True)
                save()
            helpers = [] if args.skip_helpers else [skill.id for skill in SKILLS if skill.mode == 'analysis']
            for start in range(0, len(helpers), 3):
                group = helpers[start:start + 3]
                print('Checking helpers: ' + ', '.join(group), flush=True)
                try:
                    report['checks'].extend(checks.check_helpers(group))
                except Exception as exc:
                    report['checks'].extend({'kind': 'sub_agent', 'function': function, 'status': 'FAIL',
                                             'error': str(exc)[:1500]} for function in group)
                    print(f'FAIL helper group: {str(exc)[:500]}', flush=True)
                save()
            report['model_calls'] = len(checks.calls)
    except Exception as exc:
        report['errors'].append(str(exc)[:1500])
        print(str(exc), flush=True)
    finally:
        if args.live:
            from testagent.ai_providers import provider_manager
            provider_manager.close()
        report['finished_at'] = db.now()
        report['passed'] = sum(check['status'] == 'PASS' for check in report['checks'])
        report['failed'] = sum(check['status'] == 'FAIL' for check in report['checks']) + len(report['errors'])
        save()
    print(f'{report["passed"]} passed, {report["failed"]} failed. Report: {destination}', flush=True)
    return 1 if report['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
