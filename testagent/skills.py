"""Allowlisted skill registry for TestAgent's specialized agents.

The registry is the only place that maps a public function to a Markdown file.
User input is never interpreted as a filesystem path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


SkillMode = Literal["test_cases", "analysis", "execution", "orchestration"]
SkillRequirement = Literal["none", "code", "run", "cases"]
SkillPhase = Literal["exploration", "final"]


@dataclass(frozen=True)
class AgentSkill:
    id: str
    label: str
    description: str
    file: str
    mode: SkillMode
    requires: SkillRequirement
    category: str = 'context'
    workflow: str = 'standard'
    max_cases: int = 30

    def public_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "file": self.file,
            "mode": self.mode,
            "requires": self.requires,
            "category": self.category,
            "workflow": self.workflow,
            "max_cases": self.max_cases,
            "uses_ai": self.mode != 'execution',
            "supports_sub_agent": self.mode == 'analysis',
            "instruction_files": skill_files(self.id),
        }


SKILLS: tuple[AgentSkill, ...] = (
    AgentSkill("orchestrator", "Tự động điều phối", "Hiểu yêu cầu, chọn agent phù hợp và kiểm tra ngữ cảnh cần thiết", "orchestrator.md", "orchestration", "none", 'context', 'orchestration'),
    AgentSkill("ui_automation", "Tạo UI automation", "Khảo sát luồng thật, tạo test Playwright độc lập và có assertion", "ui-automation.md", "test_cases", "none", 'automation', 'browser'),
    AgentSkill("gen_testcase", "Tạo test case", "Thiết kế bộ case có coverage, dữ liệu và điều kiện tự động hóa rõ ràng", "gen-testcase.md", "test_cases", "none", 'automation'),
    AgentSkill("automation_builder", "Chuyển case thành automation", "Bổ sung locator và thao tác thực tế cho các case đã chọn", "automation-builder.md", "test_cases", "cases", 'automation', 'browser', max_cases=20),
    AgentSkill("case_review", "Rà soát test cases", "Tìm case trùng, assertion yếu và thông tin còn thiếu trước khi chạy", "case-review.md", "analysis", "cases", 'automation'),
    AgentSkill("run_tests", "Chạy bộ test", "Thực thi các case đã chọn tuần tự hoặc song song; không cần AI", "suite-execution.md", "execution", "cases", 'automation', 'execution'),
    AgentSkill("repair_automation", "Sửa automation bị lỗi", "Dùng lỗi và quan sát mới để sửa automation, giữ nguyên kỳ vọng test", "automation-repair.md", "test_cases", "run", 'diagnostics', 'browser'),
    AgentSkill("repo_under", "Đọc repository", "Tóm tắt kiến trúc, module và rủi ro từ mã nguồn", "repo-under.md", "analysis", "code"),
    AgentSkill("report", "Viết report", "Phân tích một lượt chạy thực tế và viết báo cáo QA", "report-skill.md", "analysis", "run", 'diagnostics'),
    AgentSkill("requirement_under", "Phân tích yêu cầu", "Trích xuất tính năng, quy tắc và điểm chưa rõ", "requirement-under.md", "analysis", "none"),
    AgentSkill("test_plan", "Lập test plan", "Xác định phạm vi, rủi ro và thứ tự ưu tiên", "test-plan.md", "analysis", "none"),
    AgentSkill("unit_test", "Tạo unit test", "Đề xuất unit test và mã test để review", "unit-test.md", "test_cases", "code"),
    AgentSkill("api_test", "Tạo API test", "Tạo request có kiểm tra HTTP status từ hợp đồng API đã biết", "api-test.md", "test_cases", "none", 'automation'),
    AgentSkill("defect_analysis", "Phân tích lỗi", "Phân biệt lỗi sản phẩm, locator, dữ liệu và môi trường từ bằng chứng", "defect-analysis.md", "analysis", "run", 'diagnostics'),
    AgentSkill("regression", "Phân tích regression", "Đề xuất phạm vi regression theo thay đổi", "regression.md", "analysis", "code"),
    AgentSkill("performance", "Phân tích hiệu năng", "Đề xuất workload, metric và ngưỡng", "performance.md", "analysis", "none"),
    AgentSkill("security", "Phân tích bảo mật", "Đề xuất kiểm thử bảo mật dựa trên rủi ro", "security.md", "analysis", "none"),
    AgentSkill("exploratory", "Lập phiên exploratory", "Đề xuất charter và hành động khám phá", "exploratory.md", "analysis", "none"),
    AgentSkill("test_data", "Thiết kế test data", "Đề xuất dữ liệu hợp lệ, không hợp lệ và biên", "test-data.md", "analysis", "none"),
)

_BY_ID = {skill.id: skill for skill in SKILLS}
_SKILL_DIR = Path(__file__).with_name("agent_skills")


def get_skill(skill_id: str) -> AgentSkill:
    try:
        return _BY_ID[skill_id]
    except KeyError as exc:
        raise ValueError(f"Unknown agent function: {skill_id}") from exc


def read_skill(skill_id: str) -> str:
    """Read the Markdown instructions for an allowlisted specialized agent."""
    skill = get_skill(skill_id)
    return _read_instructions(skill.file)


def _read_instructions(filename: str) -> str:
    """Use one fail-closed reader for registered roles and shared contracts."""
    try:
        instructions = (_SKILL_DIR / filename).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Agent skill is missing: {filename}") from exc
    if not instructions:
        raise RuntimeError(f'Agent skill is empty: {filename}')
    return instructions


def skill_files(skill_id: str, *, phase: SkillPhase = 'final') -> list[str]:
    """List the exact registered documents used for a role and response phase."""
    skill = get_skill(skill_id)
    if phase not in {'exploration', 'final'}:
        raise ValueError(f'Unknown skill phase: {phase}')
    if phase == 'exploration' and skill.workflow != 'browser':
        raise ValueError(f'{skill.id} does not have a live exploration phase')
    if skill.mode == 'execution':
        return [skill.file]
    files = ['automation-core.md', skill.file]
    if skill.workflow == 'browser':
        files.append('locator-mastery.md')
        if phase == 'final':
            files.append('automation-patterns.md')
    return files


def compose_skill(skill_id: str, *, phase: SkillPhase = 'final') -> str:
    """Build an AI prompt from role instructions and phase-specific references.

    File names come exclusively from the registry and fixed shared references.
    Generation examples are intentionally excluded from browser decisions.
    Execution is deterministic and must never be routed to this AI prompt.
    """
    skill = get_skill(skill_id)
    if skill.mode == 'execution':
        raise ValueError('run_tests uses the deterministic runner, not an AI prompt')
    sections = []
    for filename in skill_files(skill_id, phase=phase):
        instructions = _read_instructions(filename)
        sections.append(f'<!-- instruction file: {filename} -->\n{instructions}')
    response = ('BrowserDecision only; do not generate a final test plan yet.' if phase == 'exploration'
                else 'GeneratedPlan only.' if skill.mode == 'test_cases'
                else 'AgentRoute only.' if skill.mode == 'orchestration'
                else 'AgentAnalysis only.')
    sections.append(f'Active phase: {phase}. Return {response}\n'
                    'The surrounding response schema takes precedence over illustrative examples. '
                    'Example accounts, locators, routes and expected values are fictional; '
                    'use facts from the current request and observations only.')
    return '\n\n'.join(sections)


def list_skills() -> list[dict]:
    return [skill.public_dict() for skill in SKILLS]


def compose_sub_agent(skill_id: str) -> str:
    """Use a registered analysis role with a narrow, read-only delegation scope."""
    if get_skill(skill_id).mode != 'analysis':
        raise ValueError('Sub-agents only support registered analysis roles')
    instructions = _read_instructions('subagent-handoff.md')
    return compose_skill(skill_id) + '\n\n<!-- instruction file: subagent-handoff.md -->\n' + instructions

