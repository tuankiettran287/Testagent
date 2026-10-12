"""Verify generated login tests can be replayed and download readable TypeScript."""
import json
import time
import urllib.request

root = 'http://127.0.0.1:18000/api'
task = json.load(urllib.request.urlopen(root + '/agent/tasks/a91e0b3b-0410-4673-972d-a52c75d78b94'))
summary = json.loads(task['summary'])
payload = {'project_id': task['project_id'], 'test_case_ids': summary['executable_ids']}
request = urllib.request.Request(root + '/tests/execute', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
run = json.load(urllib.request.urlopen(request))
for _ in range(30):
    run = json.load(urllib.request.urlopen(root + '/runs/' + run['id']))
    if run['status'] in ('COMPLETED', 'FAILED'):
        break
    time.sleep(1)
assert run['status'] == 'COMPLETED', run
assert run['summary']['counts']['PASS'] == 1
source_file = next(name for name in run['results'][0]['artifacts'] if name.endswith('.spec.ts'))
source = urllib.request.urlopen(root + '/runs/' + run['id'] + '/artifacts/' + source_file).read().decode('utf-8')
assert 'test.setTimeout(600_000)' in source and 'data-test' in source
assert run['results'][0]['title'] in source
print(json.dumps({'replay_run': run['id'], 'result': 'PASS', 'typescript_title': True}), flush=True)
