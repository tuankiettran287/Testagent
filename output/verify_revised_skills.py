"""Exercise revised prompts with the signed-in model; no target actions execute."""
import json
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from testagent import db
from testagent.ai_providers import provider_manager
from testagent.config import settings
from testagent.llm import complete_json
from testagent.orchestrator import AgentOrchestrator
from testagent.planner import ANALYSIS_SYSTEM
from testagent.schemas import AgentAnalysis
from testagent.skills import compose_skill
from testagent.ui_agent import BrowserDecision, DECISION_SYSTEM


def main():
    selection = provider_manager.resolve()
    outcomes = []
    try:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(db, 'settings', replace(settings, data_dir=Path(directory))):
                db.init_db()
                project_id = db.uid()
                project = {'name': 'Synthetic prompt verification', 'base_url': '', 'environment': 'local'}
                db.execute('INSERT INTO projects (id, name, environment, created_at) VALUES (?, ?, ?, ?)',
                           (project_id, project['name'], project['environment'], db.now()))
                for prompt, expected in (
                    ('Kiểm tra API login chịu được 2.000 concurrent users không.', 'performance'),
                    ('Viết báo cáo QA từ kết quả chạy test, nêu lỗi và hành động tiếp theo.', 'report'),
                ):
                    print('Live routing: ' + prompt, flush=True)
                    route = AgentOrchestrator().route(project_id, project, prompt, **selection)
                    assert route.skill.id == expected, route.public_dict()
                    outcomes.append({'check': 'routing', 'prompt': prompt, **route.public_dict()})
                    print(json.dumps(outcomes[-1], ensure_ascii=False), flush=True)

                print('Live BrowserDecision: synthetic login page without credentials.', flush=True)
                browser_request = {
                    'request': 'Đăng nhập bằng tài khoản test và xác nhận người dùng đã đăng nhập. Tôi chưa cung cấp tài khoản hoặc mật khẩu.',
                    'function': 'ui_automation', 'project': {**project, 'base_url': 'http://localhost:9000/login'},
                    'sources': [], 'test_cases': [], 'remaining_turns': 8,
                    'observation': {'url': 'http://localhost:9000/login', 'title': 'Fixture login',
                                    'text': 'Email Password Sign in', 'elements': [
                                        {'tag': 'input', 'label': 'Email', 'visible': True},
                                        {'tag': 'input', 'label': 'Password', 'visible': True},
                                        {'tag': 'button', 'text': 'Sign in', 'visible': True}]},
                    'performed_actions': [{'action': 'navigate', 'url': '/login'}],
                    'last_error': None,
                }
                decision = BrowserDecision.model_validate(complete_json(
                    compose_skill('ui_automation', phase='exploration') + '\n' + DECISION_SYSTEM,
                    json.dumps(browser_request, ensure_ascii=False), **selection,
                ))
                assert decision.blocked_reason and not decision.actions and not decision.done, decision.model_dump()
                outcomes.append({'check': 'missing_credentials', 'synthetic_evidence': True,
                                 'target_actions_executed': False, 'output': decision.model_dump()})
                print(json.dumps(outcomes[-1], ensure_ascii=False), flush=True)

                print('Live AgentAnalysis: useful planning without SRS/repository.', flush=True)
                analysis_request = {
                    'request': 'Lập kế hoạch kiểm thử đăng nhập cho một website. Chưa có SRS, repository hoặc tài khoản test. Nêu việc có thể chuẩn bị ngay và thông tin cụ thể còn thiếu, không khẳng định đã chạy test.',
                    'function': 'test_plan', 'project': project, 'evidence': {'sources': []},
                }
                analysis = AgentAnalysis.model_validate(complete_json(
                    ANALYSIS_SYSTEM + compose_skill('test_plan'), json.dumps(analysis_request, ensure_ascii=False), **selection,
                ))
                assert analysis.recommendations, analysis.model_dump()
                assert all(not finding.evidence_ids for finding in analysis.findings), analysis.model_dump()
                outcomes.append({'check': 'optional_sources_planning', 'target_actions_executed': False,
                                 'output': analysis.model_dump()})
                print('AgentAnalysis validated with actionable recommendations and no invented evidence IDs.', flush=True)
    finally:
        provider_manager.close()
    Path('output/revised-skills-live-result.json').write_text(
        json.dumps({'selection': selection, 'outcomes': outcomes}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('All four revised-prompt checks passed.', flush=True)


if __name__ == '__main__':
    main()
