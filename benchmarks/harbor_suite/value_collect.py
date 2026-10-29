"""Adopt explicit offline case-bank exports without promoting their scope."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .contracts import canonical, read_json, strict_json
from .value_data import Dataset


def offline(dataset, source):
    source = Path(source)
    summary = read_json(source / 'summary.json')
    if summary.get('schema') != 'ai4r-value-offline-observation:1':
        raise ValueError('original case-bank export required')
    raw = (source / 'observations.jsonl').read_bytes()
    original = [strict_json(line) for line in raw.splitlines() if line.strip()]
    if len(original) != summary['rows'] or summary.get('model_calls') != 0:
        raise ValueError('offline population differs from original summary')
    valid = summary.get('quality_credit_valid') is True and not summary.get('source_changed')
    rows = []
    for row in original:
        grade = row.get('grade') or {}
        observed = row['status'] == 'observed'
        rows.append({**row, 'case_id': row['id'], 'mode': 'offline_deterministic_capability',
            'available': observed, 'correct': grade.get('content_correct') if observed and valid else None,
            'productive_completion': grade.get('productive_completion') if observed and valid else None,
            'expected_halt_met': grade.get('expected_halt_met') if observed and valid else None,
            'native_agent_measured': False, 'protected_cc_unit_measured': False})
    data = Dataset(dataset)
    # Wrapper preserves every original UTF-8 JSONL byte and its digest; it can be
    # reconstructed exactly, unlike reserializing the parsed rows.
    retained = data.json_artifact(canonical({'format': 'utf8-jsonl',
        'original_sha256': hashlib.sha256(raw).hexdigest(), 'original_text': raw.decode('utf-8')}))
    return data.append('case_bank_observation', {'rows': rows, 'summary': summary,
        'source': retained, 'summary_source': data.artifact(source / 'summary.json'),
        'scope': 'Actual ordinary-helper and capsule-worker outputs only; no native agent, protected gate or semantic verifier.'},
        record_id='casebank-' + hashlib.sha256(canonical(summary) + raw).hexdigest())


def native(dataset, source, *, case_id, image, broker=None):
    """Grade saved native artifacts; a native terminal is not content success."""
    from .value_cases import bank
    source = Path(source)
    case = next(c for c in bank() if c['task']['id'] == case_id)
    task_raw = (source / 'project/task.json').read_bytes()
    if hashlib.sha256(task_raw).hexdigest() != case['task_sha256']:
        raise ValueError('native input differs from frozen public task')
    result = read_json(source / 'result.json')
    responses = sorted((source / 'evidence').glob('completion-*-response.json'))
    requests = sorted((source / 'evidence').glob('completion-*-request.json'))
    identity_verified = (type(result.get('model_calls')) is int
        and len(responses) == len(requests) == result['model_calls'] and bool(responses) and broker is not None)
    seen_ids = set()
    broker_sources = []
    for request_path, path in zip(requests, responses):
        response = read_json(path)
        identity_verified &= (response.get('status') == 'completed'
            and response.get('identity', {}).get('effective') == 'gpt-6.1-sol'
            and response.get('reasoning_effort') == 'medium')
        ident = response.get('request_id')
        if (not isinstance(ident, str) or len(ident) != 32
                or any(c not in '0123456789abcdef' for c in ident) or ident in seen_ids):
            identity_verified = False
            continue
        seen_ids.add(ident)
        if broker is not None:
            paths = [Path(broker) / (ident + suffix) for suffix in ('.request.json', '.response.json')]
            try:
                submitted, received = (read_json(p) for p in paths)
                packet = read_json(request_path)
                expected = {k: packet[k] for k in ('messages', 'tools')}
                actual = strict_json(submitted['prompt'].rsplit('\n', 1)[-1].encode())
                identity_verified &= (submitted['request_id'] == ident
                    and submitted['model'] == 'gpt-6.1-sol' and submitted['reasoning_effort'] == 'medium'
                    and canonical(actual) == canonical(expected) and canonical(received) == canonical(response))
                broker_sources.extend(paths)
            except (OSError, KeyError, ValueError):
                identity_verified = False
    output_path = source / 'project/response.json'
    content = None
    error = None
    try:
        from .value_cases import grade
        content = grade(case, read_json(output_path))
    except (OSError, ValueError) as exc:
        error = type(exc).__name__ + ': ' + str(exc)
    data = Dataset(dataset)
    retained = [data.artifact(p) for p in [source / 'result.json', source / 'assignment.json',
        source / 'skill-inventory.json', source / 'project/task.json', *requests, *responses, *broker_sources] if p.is_file()]
    if output_path.is_file():
        retained.append(data.json_artifact(canonical({'format': 'utf8-original-artifact',
            'original_sha256': hashlib.sha256(output_path.read_bytes()).hexdigest(),
            'original_text': output_path.read_text('utf-8')})))
    if (source / 'events.jsonl').is_file():
        raw = (source / 'events.jsonl').read_bytes()
        retained.append(data.json_artifact(canonical({'format': 'utf8-jsonl',
            'original_sha256': hashlib.sha256(raw).hexdigest(), 'original_text': raw.decode('utf-8')})))
    row = {'case_id': case_id, 'task_sha256': case['task_sha256'], 'arm': result['variant'],
        'mode': 'native_application_qualification', 'status': result['status'],
        'available': result['status'] == 'completed', 'correct': content['content_correct'] if content else None,
        'model_and_effort_verified': bool(identity_verified), 'model_calls': result.get('model_calls'),
        'selected_tool_calls': result.get('selected_tool_calls'), 'image': image,
        'grade': content, 'grading_error': error, 'cost_usd': None,
        'primary_comparison': False, 'cc_arm_available': False,
        'scope': 'Real native application, ordinary skills/tools and saved artifact; qualification only, no paired CC unit.'}
    return data.append('native_trial', {'rows': [row], 'retained_sources': retained},
        record_id='native-' + hashlib.sha256(canonical({'result': result, 'input': case['task_sha256'],
            'source': str(source.absolute()), 'broker': str(broker), 'collector_version': 2})).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--native-case')
    parser.add_argument('--image')
    parser.add_argument('--broker', type=Path)
    args = parser.parse_args()
    if args.native_case and not args.image:
        parser.error('--native-case requires the actual --image identity')
    result = (native(args.dataset, args.source, case_id=args.native_case, image=args.image, broker=args.broker)
              if args.native_case else offline(args.dataset, args.source))
    print(json.dumps({'record_id': result['id'], 'rows': len(result['value']['rows'])}))


if __name__ == '__main__':
    main()
