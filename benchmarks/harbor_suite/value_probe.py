"""Measure real utility workers/checks on clean and corrupted artifacts.

These are direct deterministic capability probes, NOT protected live gates,
semantic verifier accuracy, Harbor trials or an upstream-agent comparison.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

from .contracts import canonical
from .value_data import Dataset


def packet(data, files=()):
    return {'schema_version': '1.0.0', 'data': data, 'files': list(files),
            'trust': 'low', 'provenance': [{'id': 'probe-source', 'sha256': 'a' * 64}],
            'limitations': ['Development capability fixture; source truth is not established.']}


def fixtures():
    for size in (1, 32, 256):
        for fmt in ('csv', 'json'):
            text = ('id,value\r\n' + ''.join(f'"item,{i}",001\r\n' for i in range(size))
                    if fmt == 'csv' else json.dumps([{'id': f'item,{i}', 'value': 1} for i in range(size)]))
            source = packet({'table_request': {'file': 'source', 'format': fmt,
                'columns': ['id', 'value'], 'delimiter': ',' if fmt == 'csv' else None}},
                [{'path': 'source', 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}])
            yield 'table_normalize_v2', f'table-{fmt}-{size}', source
        for pattern, values in (('decimal', ['0.1'] * size), ('cancellation', ['1e20', '1', '-1e20'] * size),
                                ('count', ['1'] * size)):
            yield 'calculate_v2', f'calculate-{pattern}-{size}', packet({
                'table': {'columns': ['v'], 'rows': [[v] for v in values]},
                'calculation': {'columns': ['v'], 'operations': ['count', 'sum', 'mean', 'min', 'max'],
                                'numeric_mode': 'decimal_strings'}})
        yield 'markdown_report_v2', f'report-{size}', packet({'values': list(range(size)),
            'report': {'path': 'report.md', 'title': 'Measured <results>',
                       'sections': [{'heading': 'Findings', 'text': 'A bounded observation.'}],
                       'data_keys': ['values']}})


def variants(module, output):
    yield 'clean', True, copy.deepcopy(output)
    if module == 'table_normalize_v2':
        bad = copy.deepcopy(output); bad['data']['table']['rows'].pop()
        yield 'dropped_row', False, bad
        bad = copy.deepcopy(output); bad['data']['table']['rows'][0][1] = True
        yield 'type_coercion', False, bad
    elif module == 'calculate_v2':
        bad = copy.deepcopy(output); bad['data']['calculation_result']['columns']['v']['sum'] = '999'
        yield 'wrong_sum', False, bad
        bad = copy.deepcopy(output); bad['data']['calculation_result']['columns']['v']['count'] = True
        yield 'boolean_count', False, bad
    else:
        bad = copy.deepcopy(output); bad['files'][-1]['text'] += 'Unsupported extra conclusion.\n'
        bad['files'][-1]['sha256'] = hashlib.sha256(bad['files'][-1]['text'].encode()).hexdigest()
        yield 'altered_report_with_valid_hash', False, bad
        bad = copy.deepcopy(output); bad['data']['values'][0] = False
        yield 'type_coercion', False, bad
    bad = copy.deepcopy(output); bad['trust'] = 'provisional'
    yield 'trust_upgrade', False, bad
    bad = copy.deepcopy(output); bad['provenance'] = []
    yield 'lost_provenance', False, bad


async def run(dataset, *, typed=False, paired_with=None):
    data = Dataset(dataset)
    if paired_with:
        matching = [r for r in data.records() if r['id'] == paired_with and r['kind'] == 'capability_probe']
        if not typed or len(matching) != 1 or not all(r['module'].endswith('_v2') for r in matching[0]['value']['rows']):
            raise ValueError('typed run requires an exact original v2 probe record for pairing')
    root = Path(__file__).parents[2]
    def source_inventory():
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in ('jiuwenswarm/research', 'jiuwenswarm/research_contracts')
                for p in (root / folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.json')}
    before = source_inventory()
    rows = []
    sources = {}
    for module, case_id, source in fixtures():
        original_module = module
        if typed:
            module = module.removesuffix('_v2') + '_typed'
        worker = importlib.import_module('jiuwenswarm.research.capsule_extensions.' + module + '.worker')
        checker = importlib.import_module('jiuwenswarm.research.capsule_extensions.' + module + '.checks')
        # Include transitive legacy worker/check files: v2 wrappers reuse them.
        for name in (module, original_module.removesuffix('_v2')):
            for filename in ('worker.py', 'checks.py'):
                path = Path(worker.__file__).parent.parent / name / filename
                sources[str(path.relative_to(Path(__file__).parents[2]))] = hashlib.sha256(path.read_bytes()).hexdigest()
        if typed:
            path = Path(worker.__file__).parent.parent / 'typed_values.py'
            sources[str(path.relative_to(Path(__file__).parents[2]))] = hashlib.sha256(path.read_bytes()).hexdigest()
        began = time.perf_counter(); cpu = time.process_time()
        produced = await worker.execute(None, {'packet': source})
        worker_s, worker_cpu_s = time.perf_counter() - began, time.process_time() - cpu
        output = json.loads(produced['result'].data)
        for fault, valid, value in variants(original_module, output):
            began = time.perf_counter(); cpu = time.process_time()
            checks = checker.check(SimpleNamespace(output_refs={}), {'packet': source}, {'result': value})
            elapsed, cpu_s = time.perf_counter() - began, time.process_time() - cpu
            accepted = all(r['outcome'] == 'PASS' for r in checks)
            rows.append({'case_id': case_id, 'module': module, 'fault': fault,
                'mode': 'direct_deterministic_capability_probe', 'known_valid': valid,
                'checker_accepted': accepted, 'correct_decision': accepted == valid,
                'input_sha256': hashlib.sha256(canonical(source)).hexdigest(),
                'artifact_sha256': hashlib.sha256(canonical(value)).hexdigest(),
                'input_bytes': len(canonical(source)), 'output_bytes': len(canonical(value)),
                'worker_elapsed_s': worker_s, 'worker_cpu_s': worker_cpu_s,
                'checker_elapsed_s': elapsed, 'checker_cpu_s': cpu_s,
                'model_calls': 0, 'cost_usd': None, 'semantic_verifier': 'not_run',
                'checks': checks, 'input': source, 'output': value})
    after = source_inventory()
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    if changed:
        data.append('invalid_probe', {'reason': 'source_changed', 'changed': changed,
                    'sources_before': before, 'sources_after': after, 'rows': rows})
        raise RuntimeError('source changed during probe; observations retained without quality credit')
    return data.append('capability_probe', {'scope': __doc__, 'sources': sources,
        'source_inventory': before, 'source_changes': [], 'paired_with': paired_with,
        'source_scope': 'Stable checkout source during direct execution, not a qualified immutable runtime image.',
        'rows': rows})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--typed', action='store_true', help='Use additive type-preserving candidate releases')
    parser.add_argument('--paired-with', help='Exact original v2 probe record; no Cartesian repeat pairing')
    args = parser.parse_args(argv)
    result = asyncio.run(run(args.dataset, typed=args.typed, paired_with=args.paired_with))
    rows = result['value']['rows']
    print(json.dumps({'record_id': result['id'], 'artifacts': len(rows),
        'clean': sum(r['known_valid'] for r in rows),
        'invalid': sum(not r['known_valid'] for r in rows),
        'false_accepts': sum(not r['known_valid'] and r['checker_accepted'] for r in rows),
        'false_rejects': sum(r['known_valid'] and not r['checker_accepted'] for r in rows),
        'scope': 'direct deterministic checker probes; no live model or upstream comparison'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
