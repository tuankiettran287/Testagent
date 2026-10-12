"""Versioned structural context compaction; never shorten oracle text."""
from __future__ import annotations

import hashlib
import json


CONTEXT_VERSION = 'aoce-context-1'
PROMPT_VERSION = 'aoce-browser-1'


def content_hash(value) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def compact_observation(snapshot: dict) -> dict:
    """Remove absent element attributes and derived locator expressions only.

    Keep full text/ARIA, all elements, scope, literal values, false and zero.
    This is compaction of an already bounded runner observation, not retrieval.
    """
    result = {key: snapshot.get(key) for key in
              ('url', 'title', 'text', 'aria_snapshot', 'elements', 'http_status')}
    if isinstance(result['elements'], list):
        result['elements'] = [
            {key: value for key, value in element.items()
             if value is not None and value != ''
             and not (key == 'locator' and element.get('suggested_target'))}
            for element in result['elements']
        ]
    return result


def context_manifest(instructions: str, evidence: dict, *, task_id: str | None,
                     role: str, environment: str) -> dict:
    return {
        'context_version': CONTEXT_VERSION, 'prompt_version': PROMPT_VERSION,
        'prompt_sha256': hashlib.sha256(instructions.encode('utf-8')).hexdigest(),
        'task_id': task_id, 'role': role, 'environment': environment,
        'sources': [{'source_id': source.get('source_id'), 'excerpt_sha256': content_hash(source)}
                    for source in evidence.get('sources', [])],
        'case_ids': [case['id'] for case in evidence.get('test_cases', [])],
        'run_id': (evidence.get('run') or {}).get('id'),
        'usage_status': 'UNKNOWN',
        'excluded': ['unrelated_chat_history', 'absent_element_attributes', 'derived_locator_expressions'],
    }
