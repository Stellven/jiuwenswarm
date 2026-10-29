"""Collect broad telemetry only after existing original-export validation.

No inference or product request is made. Metric totals expose missingness and
count each original model/tool observation once, regardless of duplicate roles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .contracts import canonical, strict_json, validate_bundle
from .evidence import normalize_run, normalize_single_cc
from .value_data import Dataset, number


def summarize_records(records):
    seen = {}; events = []
    for row in records:
        ref = row['ref']; key = (ref['id'], ref['sha256'])
        if key in seen:
            if canonical(seen[key]['record']) != canonical(row['record']):
                raise ValueError('same original record identity has conflicting bodies')
            seen[key]['kinds'].append(row['kind'])
        else:
            value = {'ref': ref, 'kinds': [row['kind']], 'record': row['record']}
            seen[key] = value; events.append(value)
    calls = [e for e in events if set(e['kinds']) & {'model-call', 'model_call'}]
    tools = [e for e in events if set(e['kinds']) & {'tool-observation', 'tool_observation'}]
    usage = {}
    for key in ('input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_tokens', 'cost_usd'):
        values = [(e['record'].get('usage') or {}).get(key) for e in calls]
        observed = [v for v in values if number(v)]
        usage[key] = {'total': sum(observed) if len(observed) == len(values) and values else None,
                      'observed_partial_sum': sum(observed) if observed else None,
                      'observed_calls': len(observed), 'total_calls': len(values)}
    return {'model_calls': len(calls), 'tool_observations': len(tools), 'usage': usage,
            'original_events': events, 'unique_original_records': len(events),
            'cpu_seconds': None, 'gpu_seconds': None, 'peak_memory_bytes': None,
            'resource_missing_reason': 'No universal CPU/GPU/memory counters in this export; original records retained for later analysis.'}


def collect(dataset, bundle, evidence, task_key):
    index = validate_bundle(bundle)
    tasks = [t for t in index['tasks'] if t['task_key'] == task_key]
    if len(tasks) != 1:
        raise ValueError('exact frozen task key required')
    task = tasks[0]
    if task['entrypoint'] == 'single_cc':
        normalized = normalize_single_cc(evidence, task)
    elif task['entrypoint'] == 'run':
        normalized = normalize_run(evidence, task)
    else:
        raise ValueError('this telemetry path requires supported E1/E3 original-export validation')
    metrics = summarize_records(normalized['records'])
    data = Dataset(dataset)
    sources = []
    skipped = []
    for name, text in normalized['artifacts'].items():
        raw = text.encode('utf-8')
        try:
            strict_json(raw)
        except (ValueError, TypeError):
            skipped.append(name)
            continue
        sources.append({'original_path': name, 'source': data.json_artifact(raw)})
    identity = hashlib.sha256(canonical({'task': task, 'execution': normalized['execution']})).hexdigest()
    return data.append('telemetry', {'task_key': task_key, 'case_id': task['case_id'],
        'variant_id': task['variant_id'], 'repeat': task['repeat'], 'execution': normalized['execution'],
        'task_sha256': hashlib.sha256(canonical(task)).hexdigest(), 'metrics': metrics,
        'sources': sources, 'non_json_artifacts_not_copied': skipped,
        'scope': 'Validated original E1/E3 JSON records. Binary/non-JSON artifacts remain in the original export.'},
        record_id='telemetry-' + identity)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('dataset', 'bundle', 'evidence'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--task-key', required=True)
    args = parser.parse_args(argv)
    result = collect(args.dataset, args.bundle, args.evidence, args.task_key)
    print(json.dumps({'record_id': result['id'], 'records': result['value']['metrics']['unique_original_records']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
