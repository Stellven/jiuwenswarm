"""Finite public evaluations of real capsule carriers, without execution grants.

These source candidates are distinct from the governed single-function helper
registry. Public synthetic fixtures are not held-out evidence or admission.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from time import perf_counter

from ..records import encoded


@dataclass(frozen=True)
class CapsuleTarget:
    capsule_name: str
    carrier_path: str
    checks_path: str
    scope: str
    metrics: tuple[str, ...]
    public_evaluation_available: bool
    adapter_blocker: str


_TARGETS = MappingProxyType({
    name: CapsuleTarget(name, f'research/capsule_extensions/{stem}/worker.py',
        f'research/capsule_extensions/{stem}/checks.py', 'complete packet carrier',
        ('task_success', 'carrier_wall_s', 'output_bytes'), True,
        'Governed whole-capsule closure and separate development mutation declaration/grant required')
    for name, stem in [('utility.calculate', 'calculate'), ('utility.table_normalize', 'table_normalize')]
} | {
    'research.builder': CapsuleTarget('research.builder', 'research/capsules/builder_agent.py',
        'research/checks/builder_agent.py', 'full native agent and artifact build loop',
        ('task_success', 'artifact_correctness', 'pi_benchmark_elapsed_s',
         'invocation_wall_s', 'model_tokens', 'model_calls', 'tool_calls', 'execution_jobs'),
        False, 'Real governed Builder invocation and independent frozen task/Pi adapter required; model tokens may be unavailable')
})


def registered_capsule(name):
    if not isinstance(name, str) or name not in _TARGETS:
        raise ValueError('Unknown finite capsule target')
    return _TARGETS[name]


def capsule_catalog():
    """Source facts only; never synthesize Library or runtime readiness facts."""
    result = []
    root = Path(__file__).resolve().parents[2]
    for target in _TARGETS.values():
        row = asdict(target)
        carrier, checks = root / target.carrier_path, root / target.checks_path
        available = carrier.is_file() and checks.is_file()
        row.update(source_available=available, library_admission='UNKNOWN',
            parent_code_sha256=hashlib.sha256(carrier.read_bytes()).hexdigest() if carrier.is_file() else None,
            checks_sha256=hashlib.sha256(checks.read_bytes()).hexdigest() if checks.is_file() else None,
            public_fixture_count=len(public_fixtures(target.capsule_name)) if target.public_evaluation_available else 0,
            operational_rsi_available=False, measured_results=None,
            source_evolution_rsi='none' if target.public_evaluation_available else 'UNKNOWN',
            source_evolution_may_change=[] if target.public_evaluation_available else None)
        result.append(row)
    return result


def _packet(data, files=()):
    return {'schema_version': '1.0.0', 'data': data,
        'files': [{'path': path, 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
                  for path, text in files], 'trust': 'low',
        'provenance': [{'id': 'public:synthetic-input', 'sha256': '0' * 64}],
        'limitations': ['Public synthetic fixture; no private or held-out evidence.']}


def public_fixtures(name):
    """Fresh fixtures and literal expected task outputs; all labels are public."""
    registered_capsule(name)
    cases = []
    if name == 'utility.calculate':
        for ident, columns, rows, selected, operations, mode, expected in [
            ('json-numbers', ['v', 'ignored'], [[1, 'x'], [2, 'y'], [3, 'z']], ['v'],
             ['count', 'sum', 'mean', 'min', 'max'], 'json_numbers',
             {'v': {'count': 3, 'sum': '6', 'mean': '2', 'min': '1', 'max': '3'}}),
            ('decimal-order', ['a', 'b'], [['001', '-2.50'], ['2.0', '3.50'], ['3e0', '1.00']], ['b', 'a'],
             ['sum', 'count'], 'decimal_strings',
             {'b': {'sum': '2.00', 'count': 3}, 'a': {'sum': '6.0', 'count': 3}}),
            ('empty', ['v'], [], ['v'], ['count', 'sum'], 'json_numbers', {'v': {'count': 0, 'sum': '0'}}),
            ('wide-public', [f'c{i}' for i in range(12)], [[i] * 12 for i in range(2000)],
             ['c11', 'c0', 'c6'], ['count', 'sum', 'mean', 'min', 'max'], 'json_numbers',
             {key: {'count': 2000, 'sum': '1999000', 'mean': '999.5', 'min': '0', 'max': '1999'}
              for key in ('c11', 'c0', 'c6')})]:
            packet = _packet({'table': {'columns': columns, 'rows': rows},
                'calculation': {'columns': selected, 'operations': operations, 'numeric_mode': mode},
                'unrelated': {'preserve': ['exact', 7, None]}}, [('input.txt', 'retained input')])
            cases.append({'id': ident, 'packet': packet, 'expected_task_output':
                {'arithmetic': 'decimal128_half_even', 'columns': expected}})
    elif name == 'utility.table_normalize':
        for ident, columns, text, fmt, delimiter, rows in [
            ('quoted-csv', ['name', 'value'], 'name,value\r\n"a,b","001"\r\n"multi\nline",2\r\n', 'csv', ',',
             [['a,b', '001'], ['multi\nline', '2']]),
            ('json-types-order', ['b', 'a'], '[{"a":null,"b":true},{"a":2.5,"b":"001"}]', 'json', None,
             [[True, None], ['001', 2.5]]),
            ('empty-csv', ['v'], 'v\n', 'csv', ',', []),
            ('semicolon-csv', ['x', 'y'], 'x;y\nα;β\n', 'csv', ';', [['α', 'β']]),
            ('large-public', ['id', 'label'], 'id,label\n' + ''.join(f'{i},row-{i}\n' for i in range(2000)),
             'csv', ',', [[str(i), f'row-{i}'] for i in range(2000)])]:
            packet = _packet({'table_request': {'file': 'source.txt', 'format': fmt,
                'columns': columns, 'delimiter': delimiter}, 'unrelated': {'keep': True}},
                [('source.txt', text), ('notes.txt', 'retained <untrusted> content')])
            cases.append({'id': ident, 'packet': packet, 'expected_task_output': {'columns': columns, 'rows': rows}})
    else:
        raise ValueError(registered_capsule(name).adapter_blocker)
    return cases


def _carrier(name):
    # Literal installed imports: neither fixture nor caller selects a module.
    if name == 'utility.calculate':
        from jiuwenswarm.research.capsule_extensions.calculate.worker import execute
        from jiuwenswarm.research.capsule_extensions.calculate.checks import check
        return execute, check, 'calculation_result'
    if name == 'utility.table_normalize':
        from jiuwenswarm.research.capsule_extensions.table_normalize.worker import execute
        from jiuwenswarm.research.capsule_extensions.table_normalize.checks import check
        return execute, check, 'table'
    raise ValueError(registered_capsule(name).adapter_blocker)


async def evaluate_public_capsule(name):
    """Measure actual execute() only; immutable check time is excluded.

    Local clock observations describe this public evaluation, not governed
    worker timing, statistical improvement, security qualification or admission.
    No candidate source, model service, private fixture or runtime is selected.
    """
    target = registered_capsule(name)
    execute, check, output_key = _carrier(name)
    root = Path(__file__).resolve().parents[2]
    identity = {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in (target.carrier_path, target.checks_path, 'research/capsule_extensions/packet.py')}
    rows = []
    for fixture in public_fixtures(name):
        packet = fixture['packet']; before = copy.deepcopy(packet)
        started = perf_counter()
        artifact = (await execute(None, {'packet': packet}))['result']
        elapsed = perf_counter() - started
        raw = artifact.data
        if not isinstance(raw, bytes):
            raise ValueError('Actual capsule must produce serialized packet bytes')
        output = json.loads(raw)
        checks = check(SimpleNamespace(output_refs={}), {'packet': before}, {'result': output})
        exact_checks = (len(checks) == 2 and {r['check_id'] for r in checks} == {'packet_schema', 'packet_integrity'}
                        and all(r['outcome'] == 'PASS' for r in checks))
        expected_packet = copy.deepcopy(before)
        expected_packet['data'][output_key] = fixture['expected_task_output']
        preserved = packet == before and output == expected_packet
        rows.append({'fixture_id': fixture['id'], 'input_sha256': hashlib.sha256(encoded(before)).hexdigest(),
            'expected_sha256': hashlib.sha256(encoded(expected_packet)).hexdigest(),
            'task_success': bool(exact_checks and preserved), 'input_unmodified': packet == before,
            'packet_preserved': preserved, 'checks': checks, 'carrier_wall_s': elapsed,
            'output_bytes': len(raw), 'output_sha256': hashlib.sha256(raw).hexdigest()})
    return {'schema': 'ai4r-rsi-public-capsule-evaluation:1', 'capsule_name': name,
        'scope': target.scope, 'source_sha256': identity, 'fixture_visibility': 'public_synthetic',
        'governed_execution': False, 'library_admission': 'UNKNOWN', 'operational_rsi_available': False,
        'improvement_claimed': False, 'task_successes': sum(row['task_success'] for row in rows),
        'task_count': len(rows), 'rows': rows}
