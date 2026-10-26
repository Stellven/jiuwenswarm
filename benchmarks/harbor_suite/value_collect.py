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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    result = offline(args.dataset, args.source)
    print(json.dumps({'record_id': result['id'], 'rows': len(result['value']['rows'])}))


if __name__ == '__main__':
    main()
