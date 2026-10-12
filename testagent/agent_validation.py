"""Validate an AI delegation; these checks never select or replace an agent."""

from __future__ import annotations

from .browser_bridge import browser_runner_available
from .config import settings
from .db import one
from .orchestrator import RoutedTask


class OrchestrationNeedsInput(ValueError):
    """The AI-selected specialist needs input that the user has not supplied."""


def _check_code(project_id: str, project: dict, route: RoutedTask, execution_mode: str) -> None:
    if not one("SELECT id FROM sources WHERE project_id=? AND kind='code' LIMIT 1", (project_id,)):
        raise OrchestrationNeedsInput(f'{route.skill.label} cần mã nguồn. Nhập repository hoặc ZIP mã nguồn trước.')


def _check_cases(project_id: str, project: dict, route: RoutedTask, execution_mode: str) -> None:
    if not route.case_ids:
        raise OrchestrationNeedsInput(f'Chọn test cases để dùng {route.skill.label}.')
    if len(route.case_ids) > route.skill.max_cases:
        raise OrchestrationNeedsInput(f'Chọn tối đa {route.skill.max_cases} cases cho {route.skill.label} trong một tác vụ.')


def _check_run(project_id: str, project: dict, route: RoutedTask, execution_mode: str) -> None:
    if not route.run_id:
        raise OrchestrationNeedsInput(f'{route.skill.label} cần kết quả chạy test. Chạy test trước và đợi hoàn tất.')
    run = one('SELECT status FROM runs WHERE id=? AND project_id=?', (route.run_id, project_id))
    if not run or run['status'] not in {'COMPLETED', 'FAILED'}:
        raise OrchestrationNeedsInput('Đợi lượt chạy đã chọn hoàn tất trước khi phân tích.')
    if not one('SELECT id FROM run_results WHERE run_id=? LIMIT 1', (route.run_id,)):
        raise OrchestrationNeedsInput('Lượt chạy đã chọn chưa có kết quả để phân tích.')


def _check_browser(project_id: str, project: dict, route: RoutedTask, execution_mode: str) -> None:
    if not project['base_url']:
        raise OrchestrationNeedsInput('Đặt Base URL của dự án trước khi dùng browser automation.')
    if project['environment'] == 'production' and not settings.allow_production_execution:
        raise PermissionError('Execution in production is disabled')
    if not browser_runner_available():
        raise OrchestrationNeedsInput('Build browser_runner và cài Chromium trước khi dùng browser automation.')


def _check_execution(project_id: str, project: dict, route: RoutedTask, execution_mode: str) -> None:
    if execution_mode != 'run':
        raise OrchestrationNeedsInput('Yêu cầu này cần chạy test đã lưu. Chọn chế độ chạy ngay hoặc chức năng Chạy bộ test.')


_REQUIREMENT_CHECKS = {'code': _check_code, 'cases': _check_cases, 'run': _check_run}
_WORKFLOW_CHECKS = {'browser': _check_browser, 'execution': _check_execution}


def validate_delegation(project_id: str, project: dict, route: RoutedTask, execution_mode: str) -> None:
    """Apply the selected agent's registered input and execution constraints."""
    for check in (_REQUIREMENT_CHECKS.get(route.skill.requires), _WORKFLOW_CHECKS.get(route.skill.workflow)):
        if check is not None:
            check(project_id, project, route, execution_mode)
