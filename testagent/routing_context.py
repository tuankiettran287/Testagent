"""Collect project metadata for the LLM without deciding which agent to use."""

from __future__ import annotations

import json

from .db import many, one


def collect_routing_context(project_id: str, run_id: str | None, case_ids: list[str]) -> dict:
    selected_cases = []
    if case_ids:
        placeholders = ','.join('?' for _ in case_ids)
        selected_cases = many(
            f'SELECT id, title, level FROM test_cases WHERE project_id=? AND id IN ({placeholders})',
            (project_id, *case_ids),
        )
        if len(selected_cases) != len(case_ids):
            raise ValueError('Some selected cases do not belong to this project')
    if run_id:
        run = one('SELECT id, status, summary FROM runs WHERE project_id=? AND id=?', (project_id, run_id))
        if not run:
            raise ValueError('Selected run does not belong to this project')
    else:
        run = one("SELECT id, status, summary FROM runs WHERE project_id=? AND status IN ('COMPLETED','FAILED') ORDER BY requested_at DESC LIMIT 1", (project_id,))
    if run:
        run['summary'] = json.loads(run['summary'])
    return {
        'sources': many('SELECT kind, count(*) AS count FROM sources WHERE project_id=? GROUP BY kind', (project_id,)),
        'selected_cases': selected_cases,
        'run': run,
    }
