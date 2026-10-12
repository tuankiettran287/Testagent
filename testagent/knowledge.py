from __future__ import annotations

import hashlib
import re
from typing import Iterable

from .db import connection, many, now, uid


def split_text(text: str, size: int = 2400, overlap: int = 240) -> Iterable[str]:
    text = text.replace("\x00", "").strip()
    cursor = 0
    while cursor < len(text):
        end = min(len(text), cursor + size)
        if end < len(text):
            break_at = max(text.rfind("\n", cursor + size // 2, end), text.rfind(". ", cursor + size // 2, end))
            if break_at > cursor:
                end = break_at + 1
        yield text[cursor:end]
        if end >= len(text):
            break
        cursor = max(cursor + 1, end - overlap)


def add_source(project_id: str, kind: str, name: str, origin: str, content: str) -> str:
    content = content.strip()
    if not content:
        raise ValueError(f"No readable content in {name}")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    with connection() as db:
        existing = db.execute(
            "SELECT id FROM sources WHERE project_id=? AND origin=? AND sha256=?",
            (project_id, origin, digest),
        ).fetchone()
        if existing:
            return existing["id"]
        source_id = uid()
        db.execute(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (source_id, project_id, kind, name, origin, content, digest, now()),
        )
        for ordinal, chunk in enumerate(split_text(content)):
            chunk_id = uid()
            db.execute(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?)",
                (chunk_id, project_id, source_id, ordinal, chunk),
            )
            db.execute(
                "INSERT INTO chunk_fts(id, project_id, content) VALUES (?, ?, ?)",
                (chunk_id, project_id, chunk),
            )
    return source_id


def retrieve(project_id: str, query: str, limit: int = 10, kinds: tuple[str, ...] | None = None) -> list[dict]:
    kind_filter = f" AND s.kind IN ({','.join('?' for _ in kinds)})" if kinds else ""
    kind_params = tuple(kinds or ())
    words = list(dict.fromkeys(re.findall(r"[\w]{3,}", query.lower(), flags=re.UNICODE)))[:12]
    if words:
        expression = " OR ".join(f'"{word}"' for word in words)
        with connection() as db:
            rows = db.execute(
                """SELECT c.source_id, s.name, s.kind, c.content, bm25(chunk_fts) AS score
                   FROM chunk_fts JOIN chunks c ON c.id=chunk_fts.id
                   JOIN sources s ON s.id=c.source_id
                   WHERE chunk_fts MATCH ? AND c.project_id=?""" + kind_filter +
                " ORDER BY score LIMIT ?",
                (expression, project_id, *kind_params, limit),
            ).fetchall()
            if rows:
                return [dict(row) for row in rows]
    return many(
        """SELECT c.source_id, s.name, s.kind, c.content
           FROM chunks c JOIN sources s ON s.id=c.source_id
           WHERE c.project_id=?""" + kind_filter +
        " ORDER BY s.created_at DESC, c.ordinal LIMIT ?",
        (project_id, *kind_params, limit),
    )


def coverage(project_id: str) -> dict:
    sources = many("SELECT id, kind, name FROM sources WHERE project_id=? ORDER BY created_at DESC", (project_id,))
    cases = many("SELECT id, source_ids FROM test_cases WHERE project_id=?", (project_id,))
    covered = set()
    import json

    for case in cases:
        covered.update(json.loads(case["source_ids"]))
    return {
        "source_count": len(sources),
        "test_case_count": len(cases),
        "sources_with_tests": sum(source["id"] in covered for source in sources),
        "uncovered_sources": [source for source in sources if source["id"] not in covered],
    }

