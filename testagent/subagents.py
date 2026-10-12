"""Bounded, independent analysis workers with persisted parent/child tasks."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from .agent_validation import OrchestrationNeedsInput
from .config import settings
from .db import connection, now, one, uid
from .orchestrator import RoutedSubTask
from .skills import get_skill


_SLOTS = threading.BoundedSemaphore(settings.subagent_workers)


def compact_handoff(task_id: str, function: str, output: dict) -> dict:
    """Bound the lead's context while keeping full results in each child task."""
    priority = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
    findings = sorted(output.get('findings', []), key=lambda item: priority.get(item.get('severity'), 4))
    recommendations = output.get('recommendations', [])
    return {
        'task_id': task_id, 'function': function,
        'finding_count': len(findings), 'recommendation_count': len(recommendations),
        'summary': output.get('summary', '')[:900],
        'findings': [{**item, 'title': item['title'][:180], 'detail': item['detail'][:400],
                      'evidence_ids': item.get('evidence_ids', [])[:5]} for item in findings[:4]],
        'recommendations': [item[:250] for item in recommendations[:4]],
        'condensed': (len(findings) > 4 or len(recommendations) > 4
                      or len(output.get('summary', '')) > 900
                      or any(len(item['detail']) > 400 or len(item.get('evidence_ids', [])) > 5 for item in findings[:4])
                      or any(len(item) > 250 for item in recommendations[:4])),
    }


def execute_sub_agents(parent_id: str, project_id: str, plans: list[RoutedSubTask],
                       provider: str | None, model: str | None, effort: str | None,
                       work: Callable[[str, RoutedSubTask], set[str]]) -> tuple[list[dict], set[str]]:
    """Run one non-recursive analysis call per child, then return ordered handoffs.

    The lead remains pending when any worker fails; partial output is never
    represented as a completed multi-agent deliverable.
    """
    if not plans:
        return [], set()
    if len(plans) > 3 or len({plan.skill.id for plan in plans}) != len(plans):
        raise ValueError('Select at most three distinct analysis sub-agents')
    for plan in plans:
        if plan.skill.mode != 'analysis' or get_skill(plan.skill.id) != plan.skill:
            raise ValueError('Sub-agents only support registered analysis roles')
    jobs = [(uid(), plan) for plan in plans]
    with connection() as db:
        parent = db.execute('SELECT intent, parent_task_id, orchestration FROM tasks WHERE id=? AND project_id=?',
                            (parent_id, project_id)).fetchone()
        if not parent or parent['parent_task_id'] is not None:
            raise ValueError('Sub-agents require a top-level parent in the same project')
        if parent['intent'] in {plan.skill.id for plan in plans}:
            raise ValueError('Sub-agents must differ from the lead specialist')
        route = json.loads(parent['orchestration'])
        for task_id, plan in jobs:
            db.execute('''INSERT INTO tasks
                (id, project_id, parent_task_id, prompt, intent, skill_file, status,
                 created_at, ai_provider, ai_model, ai_effort)
                VALUES (?, ?, ?, ?, ?, ?, 'QUEUED', ?, ?, ?, ?)''',
                       (task_id, project_id, parent_id, plan.prompt, plan.skill.id,
                        plan.skill.file, now(), provider, model, effort))
        route['sub_tasks'] = [{**plan.public_dict(), 'task_id': task_id} for task_id, plan in jobs]
        db.execute("UPDATE tasks SET status='COLLABORATING', orchestration=?, summary=? WHERE id=?",
                   (json.dumps(route, ensure_ascii=False), json.dumps({
                       'kind': 'analysis', 'summary': f'Đang phân tích {len(jobs)} phần việc độc lập trước khi tổng hợp.'},
                       ensure_ascii=False), parent_id))

    def worker(task_id: str, plan: RoutedSubTask) -> tuple[dict, set[str], int]:
        with _SLOTS:
            started = time.monotonic()
            with connection() as db:
                db.execute("UPDATE tasks SET status='ANALYZING' WHERE id=?", (task_id,))
            try:
                valid_ids = work(task_id, plan)
                row = one('SELECT summary, status FROM tasks WHERE id=?', (task_id,))
                if row['status'] != 'COMPLETED':
                    raise RuntimeError('Sub-agent did not produce a completed analysis')
                output = json.loads(row['summary'])
                duration = round((time.monotonic() - started) * 1000)
                output['duration_ms'] = duration
                with connection() as db:
                    db.execute('UPDATE tasks SET summary=? WHERE id=?', (json.dumps(output, ensure_ascii=False), task_id))
                return compact_handoff(task_id, plan.skill.id, output), valid_ids, duration
            except Exception as exc:
                status = 'NEEDS_INPUT' if isinstance(exc, OrchestrationNeedsInput) else 'FAILED'
                with connection() as db:
                    db.execute('UPDATE tasks SET status=?, error=?, finished_at=? WHERE id=?',
                               (status, str(exc)[:2000], now(), task_id))
                raise

    started = time.monotonic()
    results, valid_ids, failures, durations = {}, set(), [], []
    with ThreadPoolExecutor(max_workers=min(len(jobs), settings.subagent_workers), thread_name_prefix='sub-agent') as pool:
        pending = {pool.submit(worker, task_id, plan): (task_id, plan) for task_id, plan in jobs}
        for future in as_completed(pending):
            task_id, plan = pending[future]
            try:
                output, ids, duration = future.result()
                results[task_id] = output
                cited_ids = {item for finding in output['findings'] for item in finding.get('evidence_ids', [])}
                valid_ids.update(ids & cited_ids)
                durations.append(duration)
            except Exception as exc:
                failures.append((plan.skill.label, exc))
    route['metrics'] = {'sub_agent_count': len(jobs), 'completed': len(results),
                        'wall_ms': round((time.monotonic() - started) * 1000),
                        'worker_ms': sum(durations)}
    with connection() as db:
        db.execute('UPDATE tasks SET orchestration=? WHERE id=?', (json.dumps(route, ensure_ascii=False), parent_id))
    if failures:
        message = 'Sub-agent chưa hoàn tất: ' + '; '.join(f'{label}: {error}' for label, error in failures)
        error_type = OrchestrationNeedsInput if all(isinstance(error, OrchestrationNeedsInput) for _, error in failures) else RuntimeError
        raise error_type(message)
    return [results[task_id] for task_id, _ in jobs], valid_ids
