from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from .config import settings


def uid() -> str:
    return str(uuid4())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(settings.data_dir / "testagent.sqlite3", timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, base_url TEXT NOT NULL DEFAULT '',
            environment TEXT NOT NULL DEFAULT 'staging', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            kind TEXT NOT NULL, name TEXT NOT NULL, origin TEXT NOT NULL, content TEXT NOT NULL,
            sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(project_id, origin, sha256)
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL, content TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
            id UNINDEXED, project_id UNINDEXED, content, tokenize='unicode61'
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            prompt TEXT NOT NULL, intent TEXT NOT NULL, skill_file TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS test_cases (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
            title TEXT NOT NULL, level TEXT NOT NULL, type TEXT NOT NULL,
            priority TEXT NOT NULL, preconditions TEXT NOT NULL, steps TEXT NOT NULL,
            expected TEXT NOT NULL, source_ids TEXT NOT NULL,
            automation TEXT, api_request TEXT, unit_test_code TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            status TEXT NOT NULL, requested_at TEXT NOT NULL, started_at TEXT,
            finished_at TEXT, summary TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS run_results (
            id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            test_case_id TEXT NOT NULL REFERENCES test_cases(id) ON DELETE CASCADE,
            status TEXT NOT NULL, duration_ms INTEGER NOT NULL,
            failure_type TEXT, message TEXT NOT NULL, artifacts TEXT NOT NULL DEFAULT '[]'
        );
        CREATE INDEX IF NOT EXISTS idx_sources_project ON sources(project_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id);
        CREATE INDEX IF NOT EXISTS idx_cases_project ON test_cases(project_id);
        CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project_id);
        CREATE INDEX IF NOT EXISTS idx_results_case ON run_results(test_case_id, run_id);
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)")}
        if "skill_file" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN skill_file TEXT NOT NULL DEFAULT ''")
        if "orchestration" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN orchestration TEXT NOT NULL DEFAULT '{}'")
        if "parent_task_id" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN parent_task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE")
        db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project_parent_created ON tasks(project_id, parent_task_id, created_at)")
        for column in ("ai_provider", "ai_model", "ai_effort"):
            if column not in columns:
                db.execute(f"ALTER TABLE tasks ADD COLUMN {column} TEXT")


def one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(query, params).fetchone()
        return dict(row) if row else None


def many(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connection() as db:
        return [dict(row) for row in db.execute(query, params).fetchall()]


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    with connection() as db:
        db.execute(query, params)


def decode_case(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("preconditions", "steps", "expected", "source_ids", "automation", "api_request"):
        row[key] = json.loads(row[key]) if row.get(key) else None
    return row

