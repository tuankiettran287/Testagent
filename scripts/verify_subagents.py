"""Verify real-model decomposition and compare the same plan in parallel/serial.

Uses a disposable database and synthetic stated requirements. No target actions
execute. Provider/model/effort come from the app's existing signed-in selection.
"""
import json
import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from testagent import db, planner
from testagent.ai_providers import provider_manager
from testagent.config import settings
from testagent.llm import complete_json
from testagent.orchestrator import AgentOrchestrator


def main():
    selection = provider_manager.resolve()
    reports = []
    try:
        with tempfile.TemporaryDirectory() as directory, patch.object(db, 'settings', replace(settings, data_dir=Path(directory))):
            db.init_db()
            project_id = db.uid()
            project = {'name': 'Synthetic planning benchmark', 'base_url': '', 'environment': 'local'}
            db.execute('INSERT INTO projects (id,name,environment,created_at) VALUES (?,?,?,?)',
                       (project_id, project['name'], project['environment'], db.now()))
            prompt = ('Lập test plan cho luồng đăng nhập theo ba phần phân tích độc lập: '
                      'rủi ro bảo mật về xác thực/phân quyền, workload hiệu năng 2.000 người dùng đồng thời, '
                      'và dữ liệu biên/không hợp lệ. Tổng hợp cả ba thành phạm vi, ưu tiên và tiêu chí nghiệm thu. '
                      'Quy tắc đã xác nhận: tài khoản hợp lệ vào dashboard, mật khẩu sai không tạo phiên; '
                      'chỉ đề xuất kế hoạch, chưa chạy test. Chưa có repository, kết quả chạy hoặc tài khoản test.')
            print('Real LLM: simple request should remain one specialist.', flush=True)
            simple = AgentOrchestrator().route(project_id, project, 'Đề xuất workload cho API login với 2.000 concurrent users.', **selection)
            assert simple.skill.id == 'performance' and not simple.sub_tasks, simple.public_dict()
            reports.append({'check': 'simple_route', **simple.public_dict()})
            print('Real LLM: single mode excludes helpers.', flush=True)
            single = AgentOrchestrator().route(project_id, project, prompt, agent_mode='single', **selection)
            assert not single.sub_tasks, single.public_dict()
            reports.append({'check': 'single_route', **single.public_dict()})
            print('Real LLM: decompose the compound planning request.', flush=True)
            route = AgentOrchestrator().route(project_id, project, prompt, **selection)
            assert route.skill.id == 'test_plan' and len(route.sub_tasks) >= 2, route.public_dict()
            print(json.dumps(route.public_dict(), ensure_ascii=False), flush=True)
            reports.append({'check': 'compound_route', **route.public_dict()})
            # Freeze the actual AI-selected plan for a comparable worker workload.
            for label, limit in (('parallel', 3), ('serial', 1)):
                task_id = db.uid()
                db.execute('INSERT INTO tasks (id,project_id,prompt,intent,skill_file,status,created_at) VALUES (?,?,?,?,?,?,?)',
                           (task_id, project_id, prompt, 'orchestrator', 'orchestrator.md', 'CREATED', db.now()))
                events = []
                event_lock = threading.Lock()
                def timed_complete(system, user, provider=None, model=None, effort=None):
                    function = json.loads(user)['function']
                    started = time.monotonic()
                    output = complete_json(system, user, provider, model, effort)
                    with event_lock:
                        events.append({'function': function, 'start': started, 'end': time.monotonic()})
                    return output
                print(f'Real workers + lead: {label}', flush=True)
                with patch.object(planner, 'AgentOrchestrator') as factory, patch.object(planner, 'complete_json', side_effect=timed_complete), patch('testagent.subagents.settings', replace(settings, subagent_workers=limit)), patch('testagent.subagents._SLOTS', threading.BoundedSemaphore(limit)):
                    factory.return_value.route.return_value = route
                    planner.run_task(task_id, project_id, prompt, 'orchestrator', **selection, execution_mode='generate')
                task = db.one('SELECT * FROM tasks WHERE id=?', (task_id,))
                assert task['status'] == 'COMPLETED', task['error']
                children = db.many('SELECT * FROM tasks WHERE parent_task_id=?', (task_id,))
                assert len(children) == len(route.sub_tasks) and all(child['status'] == 'COMPLETED' for child in children)
                for child in children:
                    assert child['ai_provider'] == selection['provider'] and child['ai_model'] == selection['model']
                    output = json.loads(child['summary'])
                    assert all(not finding['evidence_ids'] for finding in output['findings']), output
                helpers = [event for event in events if event['function'] != route.skill.id]
                overlap = any(max(a['start'], b['start']) < min(a['end'], b['end']) for index, a in enumerate(helpers) for b in helpers[index + 1:])
                assert overlap == (label == 'parallel'), events
                metrics = json.loads(task['orchestration'])['metrics']
                print(json.dumps({'mode': label, 'overlap': overlap, **metrics}), flush=True)
                reports.append({'check': label, 'overlap': overlap, 'metrics': metrics,
                                'model_calls_excluding_frozen_route': len(events),
                                'children': [json.loads(child['summary']) for child in children],
                                'lead_output': json.loads(task['summary'])})
            assert not db.many('SELECT * FROM runs') and not db.many('SELECT * FROM test_cases')
    finally:
        provider_manager.close()
    Path('output').mkdir(exist_ok=True)
    Path('output/subagents-live-result.json').write_text(json.dumps({
        'selection': selection, 'synthetic_context': True, 'target_actions_executed': False,
        'note': 'One sample per mode, real model calls. Timing is observational; token/cost totals are unavailable.',
        'checks': reports,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Real-model routing, worker isolation, handoff and comparison passed.', flush=True)


if __name__ == '__main__':
    main()
