from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from .automation import checked_url, validate_automation
from .browser_bridge import BrowserRunnerError, browser_runner_available, invoke_browser
from .config import settings
from .db import connection, decode_case, many, now, one, uid
from .schemas import ApiRequest, Automation, RunCreate
from .readiness import case_readiness


def _browser_case(case: dict, base_url: str, artifact_dir: Path) -> tuple[str, str, list[str]]:
    automation = Automation.model_validate(case["automation"])
    validate_automation(automation, base_url)
    result = invoke_browser(
        "execute",
        {
            "baseUrl": base_url,
            "caseId": case["id"],
            "title": case["title"],
            "artifactDir": str(artifact_dir.resolve()),
            "automation": automation.model_dump(exclude_none=True),
        },
        timeout=600,
    )
    status = result.get("status")
    if status not in {"PASS", "FAIL", "ERROR", "TIMEOUT"}:
        raise ValueError("TypeScript browser runner returned an invalid status")
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list) or any(not isinstance(item, str) or Path(item).name != item for item in artifacts):
        raise ValueError("TypeScript browser runner returned invalid artifact names")
    return status, str(result.get("message", ""))[:1500], artifacts


def _api_case(case: dict, base_url: str) -> tuple[str, str, list[str]]:
    request = ApiRequest.model_validate(case["api_request"])
    url = checked_url(base_url, request.path)
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        response = client.request(
            request.method, url, headers=request.headers,
            json=request.body if isinstance(request.body, (dict, list)) else None,
            content=request.body if isinstance(request.body, str) else None,
        )
    if response.status_code == request.expected_status:
        return "PASS", f"HTTP {response.status_code} matched expected status", []
    return "FAIL", f"Expected HTTP {request.expected_status}, received {response.status_code}: {response.text[:500]}", []


def _validate_run_cases(project: dict | None, cases: list[dict]) -> None:
    if not project:
        raise ValueError('Project not found')
    if project['environment'] == 'production' and not settings.allow_production_execution:
        raise PermissionError('Execution in production is disabled')
    for case in cases:
        ready = case_readiness(case, project['base_url'])
        if ready['status'] != 'ready':
            raise ValueError(case['title'] + ': ' + ready['reason'])
    if any(case['automation'] for case in cases) and not browser_runner_available():
        raise BrowserRunnerError('Build browser_runner and install Chromium before execution')


def prepare_run(project_id: str, case_ids: list[str], mode: str = 'sequential', workers: int = 3) -> str:
    project = one('SELECT * FROM projects WHERE id=?', (project_id,))
    if not case_ids or len(case_ids) > 30 or mode not in {'sequential', 'parallel'} or not 1 <= workers <= 4:
        raise ValueError('Select 1–30 test cases and a valid execution mode/worker limit')
    case_ids = list(dict.fromkeys(case_ids))
    placeholders = ','.join('?' for _ in case_ids)
    cases = [decode_case(row) for row in many(f'SELECT * FROM test_cases WHERE project_id=? AND id IN ({placeholders})', (project_id, *case_ids))]
    if len(cases) != len(case_ids):
        raise ValueError('Some test cases do not belong to this project')
    _validate_run_cases(project, cases)
    run_id = uid()
    summary = {'test_case_ids': case_ids, 'mode': mode, 'workers': min(workers, len(cases)) if mode == 'parallel' else 1,
               'total': len(cases), 'completed': 0, 'counts': {'PASS': 0, 'FAIL': 0, 'ERROR': 0, 'TIMEOUT': 0}}
    with connection() as db:
        db.execute("INSERT INTO runs (id, project_id, status, requested_at, summary) VALUES (?, ?, 'QUEUED', ?, ?)",
                   (run_id, project_id, now(), json.dumps(summary)))
    return run_id


def _execute_case(case: dict, project: dict, artifact_dir: Path) -> tuple:
    started = time.monotonic()
    try:
        if case['automation']:
            status, message, artifacts = _browser_case(case, project['base_url'], artifact_dir)
        elif case['api_request']:
            status, message, artifacts = _api_case(case, project['base_url'])
        else:
            status, message, artifacts = 'ERROR', 'No executable browser DSL or API request', []
    except (httpx.TimeoutException, TimeoutError) as exc:
        status, message, artifacts = 'TIMEOUT', str(exc), []
    except Exception as exc:
        status, message, artifacts = 'ERROR', str(exc)[:1500], []
    return case['id'], status, message, artifacts, int((time.monotonic() - started) * 1000)


def execute_run(run_id: str) -> None:
    # A conditional database write claims delivery across threads/processes.
    # Repeated deliveries of a running or finished run must have no effects.
    with connection() as db:
        claimed = db.execute("UPDATE runs SET status='RUNNING', started_at=? WHERE id=? AND status='QUEUED'",
                             (now(), run_id)).rowcount
    if not claimed:
        return
    try:
        _execute_run(run_id)
    except Exception as exc:
        # A setup/storage error must not leave the UI polling a queued run forever.
        run = one('SELECT summary FROM runs WHERE id=?', (run_id,))
        if run:
            try:
                summary = json.loads(run['summary'])
            except (ValueError, TypeError):
                summary = {}
            if not isinstance(summary, dict):
                summary = {}
            summary['error'] = str(exc)[:1500]
            with connection() as db:
                db.execute("UPDATE runs SET status='FAILED', finished_at=?, summary=? WHERE id=? AND status='RUNNING'", (now(), json.dumps(summary), run_id))


def _execute_run(run_id: str) -> None:
    run = one("SELECT * FROM runs WHERE id=?", (run_id,))
    project = one("SELECT * FROM projects WHERE id=?", (run["project_id"],))
    summary = json.loads(run['summary'])
    request = RunCreate.model_validate({'project_id': run['project_id'], 'test_case_ids': summary['test_case_ids'],
                                        'mode': summary.get('mode', 'sequential'), 'workers': summary.get('workers', 1)})
    case_ids = request.test_case_ids
    placeholders = ",".join("?" for _ in case_ids)
    stored = {row['id']: decode_case(row) for row in many(
        f"SELECT * FROM test_cases WHERE project_id=? AND id IN ({placeholders})",
        (run["project_id"], *case_ids),
    )}
    if len(stored) != len(case_ids):
        raise ValueError('Some queued test cases no longer belong to this project')
    cases = [stored[case_id] for case_id in case_ids]
    # Admission and delivery may be separated by project/case edits.
    # Check the exact payload that will run before starting any case.
    _validate_run_cases(project, cases)
    artifact_dir = settings.data_dir / "artifacts" / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    counts = {"PASS": 0, "FAIL": 0, "ERROR": 0, "TIMEOUT": 0}
    summary.update(total=len(cases), completed=0, counts=counts)

    def record(result):
        case_id, status, message, artifacts, duration = result
        counts[status] += 1
        summary['completed'] += 1
        failure_type = None if status == "PASS" else ("ASSERTION" if status == "FAIL" else "TIMEOUT" if status == "TIMEOUT" else "ENVIRONMENT_OR_AUTOMATION")
        with connection() as db:
            db.execute(
                "INSERT INTO run_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (uid(), run_id, case_id, status, duration, failure_type, message, json.dumps(artifacts)),
            )
            db.execute('UPDATE runs SET summary=? WHERE id=?', (json.dumps(summary), run_id))
    if request.mode == 'parallel':
        with ThreadPoolExecutor(max_workers=request.workers) as executor:
            futures = [executor.submit(_execute_case, case, project, artifact_dir) for case in cases]
            for future in as_completed(futures):
                record(future.result())
    else:
        for case in cases:
            record(_execute_case(case, project, artifact_dir))
    final_status = "COMPLETED" if counts["FAIL"] + counts["ERROR"] + counts["TIMEOUT"] == 0 else "FAILED"
    with connection() as db:
        db.execute(
            "UPDATE runs SET status=?, finished_at=?, summary=? WHERE id=?",
            (final_status, now(), json.dumps(summary), run_id),
        )

