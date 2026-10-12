"""Explain whether a stored test can run before admitting it to an execution queue."""
from .automation import checked_url, validate_automation
from .schemas import ApiRequest, Automation


def case_readiness(case: dict, base_url: str) -> dict:
    engine = 'playwright' if case.get('automation') else 'api' if case.get('api_request') else None
    if case.get('automation') is not None and case.get('api_request') is not None:
        return {'status': 'invalid', 'engine': None, 'reason': 'A test case must define only one execution engine.'}
    if not engine:
        return {'status': 'manual', 'engine': None, 'reason': 'Chưa có automation. Chọn case và dùng Chuyển case thành automation.'}
    if not base_url:
        return {'status': 'needs_input', 'engine': engine, 'reason': 'Cần cấu hình Base URL trước khi chạy.'}
    try:
        if engine == 'playwright':
            automation = Automation.model_validate(case['automation'])
            validate_automation(automation, base_url)
            if automation.actions[0].action != 'navigate':
                return {'status': 'needs_input', 'engine': engine, 'reason': 'Test cần bước mở trang đầu tiên để chạy độc lập.'}
            if not any(action.action.startswith('assert_') for action in automation.actions):
                return {'status': 'needs_input', 'engine': engine, 'reason': 'Test chưa có assertion kiểm tra kết quả mong đợi.'}
        else:
            request = ApiRequest.model_validate(case['api_request'])
            checked_url(base_url, request.path)
    except (ValueError, TypeError) as exc:
        return {'status': 'invalid', 'engine': engine, 'reason': str(exc)[:500]}
    return {'status': 'ready', 'engine': engine, 'reason': 'Có thể chạy độc lập bằng Playwright.' if engine == 'playwright' else 'Có thể chạy request và kiểm tra HTTP status.'}
