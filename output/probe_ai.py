import json
import sys
from pathlib import Path
from testagent.cli_transport import run_cli, executable

if len(sys.argv) > 1:
    from testagent.ai_providers import provider_manager
    provider, model = sys.argv[1:3]
    try:
        result = provider_manager.complete('Return exactly one JSON object with summary and cases. No tools.', 'Reply with {"summary":"CLI integration verified", "cases":[]}', provider, model)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        provider_manager.close()
    sys.exit()

message = json.dumps({'type': 'control_request', 'request_id': 'models', 'request': {'subtype': 'initialize'}}) + '\n'
result = run_cli(executable('claude') + ['-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose', '--tools', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}'], cwd=Path('.'), input_text=message, timeout=25)
for line in result[1].splitlines():
    data = json.loads(line)
    response = data.get('response', {}).get('response', {})
    print('CLAUDE', result[0], list(response), response.get('models'), response.get('account'))
result = run_cli(executable('agy') + ['models'], cwd=Path('.'), terminal=True)
print('AGY', result[0], result[1][-1600:])
