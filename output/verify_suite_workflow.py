"""Verify native CLI conversion, review-before-run, and isolated browser batch execution."""
import json
import time
import urllib.request
from pathlib import Path

root = 'http://127.0.0.1:18000/api'
project_id = '85d866f3-d9a8-472d-90c7-9ade1d231f0c'
case_id = '52c70f49-5acf-4844-8776-57a8eb59c073'
replay_id = '6611a75d-8718-4132-9bbe-db55af7f36d3'

def get(path):
    return json.load(urllib.request.urlopen(root + path, timeout=30))

def post(path, payload):
    request = urllib.request.Request(root + path, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    return json.load(urllib.request.urlopen(request, timeout=30))

def wait(path, terminal, seconds=600):
    deadline, previous = time.monotonic() + seconds, None
    while time.monotonic() < deadline:
        item = get(path)
        if item['status'] != previous:
            print(json.dumps({'id': item['id'], 'status': item['status']}), flush=True)
            previous = item['status']
        if item['status'] in terminal:
            return item
        time.sleep(2)
    raise AssertionError('Work did not finish in time')

state = get('/ai/providers')
assert state['ready']
original = get('/tests/' + case_id)
initial_cases = get('/projects/' + project_id + '/tests')
initial_runs = get('/projects/' + project_id + '/runs')
task = post('/agent/tasks', {'project_id': project_id, 'function': 'automation_builder', 'case_ids': [case_id], 'execution_mode': 'generate', 'prompt': 'Chuyển case đăng nhập đã chọn thành Playwright automation chạy độc lập. Dùng tài khoản standard_user / secret_sauce công bố trên trang. Quan sát giao diện sau đăng nhập để xác nhận trang Products và URL inventory. Giữ nguyên mục tiêu, tiêu đề và kỳ vọng của case. Tạo automation để xem trước, chưa chạy xác nhận.'})
task = wait('/agent/tasks/' + task['id'], {'READY', 'COMPLETED', 'NEEDS_INPUT', 'FAILED'})
Path('output/suite-builder-result.json').write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding='utf-8')
assert task['status'] == 'READY', task
output = json.loads(task['summary'])
assert output['case_ids'] == [case_id] and output['executable_ids'] == [case_id], output
assert output['execution'] is None and not output.get('run_id'), output
assert len(get('/projects/' + project_id + '/tests')) == len(initial_cases)
assert len(get('/projects/' + project_id + '/runs')) == len(initial_runs)
updated = get('/tests/' + case_id)
assert updated['title'] == original['title'] and updated['expected'] == original['expected']
assert updated['readiness']['status'] == 'ready'
actions = updated['automation']['actions']
assert sum(action['action'] == 'fill' for action in actions) >= 2
assert any(action['action'] == 'click' for action in actions)
assert any(action['action'] == 'assert_url' and 'inventory' in action['url'] for action in actions)
run_ids = []
for ids, mode, workers in [([case_id], 'sequential', 1), ([case_id, replay_id], 'parallel', 2)]:
    created = post('/tests/execute', {'project_id': project_id, 'test_case_ids': ids, 'mode': mode, 'workers': workers})
    run = wait('/runs/' + created['id'], {'COMPLETED', 'FAILED'})
    assert run['status'] == 'COMPLETED', run
    assert run['summary']['counts']['PASS'] == len(ids)
    assert run['summary']['completed'] == len(ids) and run['summary']['mode'] == mode
    assert run['summary']['workers'] == workers
    for result in run['results']:
        assert any(name.endswith('.spec.ts') for name in result['artifacts'])
        assert any(name.endswith('trace.zip') for name in result['artifacts'])
        assert any(name.endswith('.webm') for name in result['artifacts'])
    run_ids.append(run['id'])
    print(json.dumps({'mode': mode, 'run_id': run['id'], 'PASS': len(ids)}), flush=True)
assert get('/ai/providers')['selection'] == state['selection']
assert get('/projects/' + project_id + '/sources') == []
Path('output/suite-workflow-result.json').write_text(json.dumps({'task_id': task['id'], 'case_id': case_id, 'run_ids': run_ids, 'cases_unchanged': True, 'ready_before_run': True, 'native_ai': state['selection']}, indent=2), encoding='utf-8')
