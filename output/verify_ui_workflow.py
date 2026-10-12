"""Run the user's Sauce Demo login goal through the local application."""
import json
import time
import urllib.request
from pathlib import Path


root = 'http://127.0.0.1:18000/api'
project_id = '85d866f3-d9a8-472d-90c7-9ade1d231f0c'


def get(path):
    return json.load(urllib.request.urlopen(root + path, timeout=30))


state = get('/ai/providers')
assert state['ready'], 'Connect an AI account in the application first'
assert get('/projects/' + project_id)['base_url'].startswith('https://www.saucedemo.com')
payload = {'project_id': project_id, 'function': 'ui_automation',
           'prompt': 'Đăng nhập trang web bằng tài khoản demo được công bố trên trang, xác nhận đã vào được trang sản phẩm. Tự quan sát sau khi đăng nhập để chọn locator và assertion. Lên kịch bản và chạy đúng một test automation cho luồng đăng nhập thành công.'}
request = urllib.request.Request(root + '/agent/tasks', data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
task = json.load(urllib.request.urlopen(request, timeout=30))
print(json.dumps({'task_id': task['id'], 'status': task['status'], 'ai_effort': task['ai_effort']}), flush=True)
deadline, previous = time.monotonic() + 600, None
while time.monotonic() < deadline:
    task = get('/agent/tasks/' + task['id'])
    output = json.loads(task['summary']) if task['summary'] else {}
    if task['status'] != previous:
        print(json.dumps({'status': task['status'], 'phase': output.get('phase')}, ensure_ascii=False), flush=True)
        previous = task['status']
    if task['status'] in {'COMPLETED', 'FAILED', 'NEEDS_INPUT'}:
        break
    time.sleep(2)
else:
    raise AssertionError('Agent task did not finish within ten minutes')
Path('output/ui-workflow-result.json').write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding='utf-8')
assert task['status'] == 'COMPLETED', {'error': task['error'], 'output': output}
assert output['execution']['counts']['PASS'] == 1 and output['execution']['total'] == 1, output
assert output['manual_count'] == 0, output
cases = [case for case in get('/projects/' + project_id + '/tests') if case['task_id'] == task['id']]
assert len(cases) == 1
actions = cases[0]['automation']['actions']
assert sum(action['action'] == 'fill' for action in actions) >= 2, actions
assert any(action['action'] == 'click' for action in actions), actions
assert any(action['action'] == 'assert_url' and 'inventory' in action['url'] for action in actions) or any(action['action'] == 'assert_text' and 'Products' in action.get('value', '') for action in actions), actions
run = get('/runs/' + output['run_id'])
artifacts = run['results'][0]['artifacts']
assert any(name.endswith('.spec.ts') for name in artifacts)
assert any(name.endswith('-trace.zip') for name in artifacts)
assert any(name.endswith('.webm') for name in artifacts)
print(json.dumps({'task_id': task['id'], 'run_id': run['id'], 'result': 'PASS', 'fills': 2, 'clicks': True,
                  'post_login_assertion': True, 'artifacts': artifacts}), flush=True)
