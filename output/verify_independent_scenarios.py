"""Convert two existing manual cases using native AI, then replay them in parallel."""
import json
import time
import urllib.request
from pathlib import Path

root = 'http://127.0.0.1:18000/api'
project_id = '85d866f3-d9a8-472d-90c7-9ade1d231f0c'
ids = ['5f763b04-1d21-455b-8265-9bc7e5d81b0c', '660b38a8-21c7-42e0-b486-92c02a2f6ad9']
def get(path):
    return json.load(urllib.request.urlopen(root + path, timeout=30))
def post(path, payload):
    request = urllib.request.Request(root + path, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    return json.load(urllib.request.urlopen(request, timeout=30))
def wait(path, terminal):
    deadline, previous = time.monotonic() + 600, None
    while time.monotonic() < deadline:
        item = get(path)
        if item['status'] != previous:
            print(json.dumps({'id': item['id'], 'status': item['status']}), flush=True)
            previous = item['status']
        if item['status'] in terminal:
            return item
        time.sleep(2)
    raise AssertionError('Task did not finish within ten minutes')

originals = {case_id: get('/tests/' + case_id) for case_id in ids}
task = post('/agent/tasks', {'project_id': project_id, 'function': 'automation_builder', 'case_ids': ids, 'execution_mode': 'generate', 'prompt': 'Tạo automation cho đúng hai case đã chọn: đăng nhập thành công standard_user/secret_sauce và bị từ chối khi dùng standard_user/secret_sauc (mật khẩu thiếu ký tự cuối). Khám phá độc lập, dùng reset_browser giữa hai tình huống. Với case đúng kiểm tra URL inventory và Products; với case sai kiểm tra thông báo lỗi quan sát được và vẫn ở trang đăng nhập. Giữ ID, mục tiêu và kỳ vọng của case gốc. Chỉ tạo để review, chưa chạy xác nhận.'})
task = wait('/agent/tasks/' + task['id'], {'READY', 'FAILED', 'NEEDS_INPUT', 'COMPLETED'})
Path('output/independent-scenarios-task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding='utf-8')
assert task['status'] == 'READY', task
output = json.loads(task['summary'])
assert set(output['executable_ids']) == set(ids) and not output.get('run_id'), output
for case_id in ids:
    case = get('/tests/' + case_id)
    assert case['title'] == originals[case_id]['title'] and case['expected'] == originals[case_id]['expected']
    assert case['readiness']['status'] == 'ready'
    assert case['automation']['actions'][0]['action'] == 'navigate'
run = post('/tests/execute', {'project_id': project_id, 'test_case_ids': ids, 'mode': 'parallel', 'workers': 2})
run = wait('/runs/' + run['id'], {'COMPLETED', 'FAILED'})
Path('output/independent-scenarios-run.json').write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding='utf-8')
assert run['status'] == 'COMPLETED' and run['summary']['counts']['PASS'] == 2, run
print(json.dumps({'task_id': task['id'], 'run_id': run['id'], 'positive_negative': True, 'parallel_PASS': 2}), flush=True)
