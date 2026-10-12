"""Check real LLM delegation with the app's currently signed-in provider."""
import json
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from testagent import db
from testagent.ai_providers import provider_manager
from testagent.config import settings
from testagent.orchestrator import AgentOrchestrator


def main():
    selection = provider_manager.resolve()
    checks = [
        ('Kiểm tra API login chịu được 2.000 concurrent users không.', 'performance'),
        ('Viết báo cáo QA từ kết quả chạy test, nêu lỗi và hành động tiếp theo.', 'report'),
    ]
    results = []
    try:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(db, 'settings', replace(settings, data_dir=Path(directory))):
                db.init_db()
                project_id = db.uid()
                project = {'name': 'LLM routing verification', 'base_url': '', 'environment': 'local'}
                db.execute('INSERT INTO projects (id, name, environment, created_at) VALUES (?, ?, ?, ?)',
                           (project_id, project['name'], project['environment'], db.now()))
                orchestrator = AgentOrchestrator()
                for prompt, expected in checks:
                    print(f"Calling signed-in {selection['provider']} / {selection['model']} for: {prompt}", flush=True)
                    route = orchestrator.route(project_id, project, prompt, **selection)
                    result = {'prompt': prompt, 'expected': expected, **route.public_dict()}
                    results.append(result)
                    print(json.dumps(result, ensure_ascii=False), flush=True)
                    if route.skill.id != expected:
                        raise AssertionError(f'Expected {expected}, got {route.skill.id}')
    finally:
        provider_manager.close()
    Path('output/orchestrator-live-result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Both real-provider routing checks passed.', flush=True)


if __name__ == '__main__':
    main()
