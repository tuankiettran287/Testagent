import json
import tempfile
from pathlib import Path
from testagent.cli_transport import CodexRpc, run_cli, executable
from testagent.config import settings

with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    rpc = CodexRpc(settings.codex_binary, work)
    try:
        models = rpc.request('model/list', {'limit': 100, 'includeHidden': False})['data']
        print(json.dumps({'codex': [{'model': row['model'], 'efforts': row.get('supportedReasoningEfforts'), 'default_effort': row.get('defaultReasoningEffort')} for row in models]}, ensure_ascii=False), flush=True)
    finally:
        rpc.close()
    message = {'type': 'control_request', 'request_id': 'catalog', 'request': {'subtype': 'initialize'}}
    _, output, _ = run_cli([*executable(settings.claude_binary, '@anthropic-ai/claude-code/cli.js'), '-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose', '--tools', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}'], cwd=work, input_text=json.dumps(message) + '\n')
    for line in output.splitlines():
        response = json.loads(line).get('response', {})
        if response.get('request_id') == 'catalog':
            print(json.dumps({'claude_models': response.get('response', {}).get('models', [])}, ensure_ascii=False), flush=True)
