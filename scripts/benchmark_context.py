"""Replay identical synthetic snapshots; measure bytes, never infer billed tokens."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from testagent.context import CONTEXT_VERSION, compact_observation, content_hash


def benchmark() -> dict:
    samples = []
    for index in range(3):
        snapshot = {
            'url': 'http://127.0.0.1/fixture', 'title': 'AOCE synthetic directory',
            'http_status': 200, 'text': f'Owned E2E-AOCE-{index} department QA',
            'aria_snapshot': f'- dialog "Create employee"\n- row "E2E-AOCE-{index} QA"',
            'elements': [
                {'tag': 'button', 'role': 'button', 'name': f'Save {control}', 'id': None,
                 'label': None, 'placeholder': None, 'testid': None, 'href': None, 'pattern': None,
                 'min': None, 'max': None, 'minlength': None, 'maxlength': None,
                 'text': f'Save {control}', 'visible': True, 'disabled': False,
                 'suggested_target': {'role': 'button', 'name': f'Save {control}',
                                      'scope': {'role': 'dialog', 'name': 'Create employee'}},
                 'locator': f'page.getByRole("dialog", {{name:"Create employee"}}).getByRole("button", {{name:"Save {control}"}})',
                 'match_count': 1}
                for control in range(10 + index)
            ],
        }
        for variant in ('baseline', 'optimized'):
            start = time.perf_counter_ns()
            context = dict(snapshot) if variant == 'baseline' else compact_observation(snapshot)
            elapsed = time.perf_counter_ns() - start
            # Quality before cost: preserve every actual value and every element.
            quality = all(context[key] == snapshot[key] for key in ('url', 'title', 'text', 'aria_snapshot', 'http_status'))
            quality = quality and len(context['elements']) == len(snapshot['elements'])
            for before, after in zip(snapshot['elements'], context['elements']):
                quality = quality and all(after.get(key) == value for key, value in before.items()
                                          if value is not None and value != '' and key != 'locator')
            samples.append({'sample': index + 1, 'variant': variant, 'input_sha256': content_hash(snapshot),
                            'context_sha256': content_hash(context), 'quality_gate': quality,
                            'serialized_bytes': len(json.dumps(context, ensure_ascii=False).encode('utf-8')),
                            'compaction_ns': elapsed})
    sizes = {variant: [row['serialized_bytes'] for row in samples if row['variant'] == variant]
             for variant in ('baseline', 'optimized')}
    return {'mode': 'SYNTHETIC_CONTEXT_REPLAY', 'context_version': CONTEXT_VERSION,
            'samples_per_variant': 3, 'samples': samples,
            'quality_gate': all(row['quality_gate'] for row in samples),
            'median_bytes': {key: statistics.median(value) for key, value in sizes.items()},
            'byte_reduction_percent': round(100 * (1 - sum(sizes['optimized']) / sum(sizes['baseline'])), 2),
            'model_calls': 0, 'usage_status': 'NOT_APPLICABLE', 'billed_token_savings': 'UNKNOWN',
            'monetary_savings': 'UNKNOWN',
            'limitations': ['Synthetic snapshots; not a model quality or production reliability benchmark.',
                           'Compaction timing excludes model, browser, queue, install and cleanup time.',
                           'Preserving injected text as data does not prove a model resists injection.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output/aoce/context-benchmark.json'))
    args = parser.parse_args()
    report = benchmark()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Context bytes reduced {report['byte_reduction_percent']}%; quality gate: {report['quality_gate']}")
    return 0 if report['quality_gate'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
