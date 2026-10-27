"""Finite public evaluations of real capsule carriers, without execution grants.

These source candidates are distinct from the governed single-function helper
registry. Public synthetic fixtures are not held-out evidence or admission.

Packet capsule targets are discovered from data: an installed
``research/capsule_extensions/<stem>/fixtures/manifest.json`` registers the
capsule ``<stem>`` (its ``worker.py`` carrier and ``checks.py`` checker) and
names its fixture sets. No capsule name is special-cased here.

Fixture sets and their consumers:

* ``public`` -- the historical baseline cases. ``public_fixtures(name)`` returns
  exactly these (byte-identical to the original literal definitions); the
  visible proposer context, publication and historical proofs pin them.
* ``public_extended`` -- harder public cases (edge cases, ties, unicode, large
  tables). Visible to the proposer through score feedback; evaluated together
  with ``public`` by the improvement loop.
* ``held_out`` -- evaluated by the loop, never shown to the proposer. Only
  their opaque ids and pass/fail reach feedback (see ``capsule_objective``).

The ``fixtures/`` directory name is also a runtime-forbidden tree in
``capsule_runtime._path``, so fixture data can never enter a sandbox runtime.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import importlib
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from time import perf_counter

from ..records import encoded

FIXTURE_SCHEMA = 'ai4r-rsi-capsule-fixtures:1'
FIXTURE_SET_SCHEMA = 'ai4r-rsi-capsule-fixture-set:1'
FIXTURE_SETS = ('public', 'public_extended', 'held_out')
OBJECTIVE = 'correctness_then_latency_above_noise'
MAX_CAPTURED_OUTPUT_CHARS = 64 * 1024
_EXTENSIONS = Path(__file__).resolve().parents[2] / 'research' / 'capsule_extensions'
_PACKAGE = 'jiuwenswarm.research.capsule_extensions'


@dataclass(frozen=True)
class CapsuleTarget:
    capsule_name: str
    carrier_path: str
    checks_path: str
    scope: str
    metrics: tuple[str, ...]
    public_evaluation_available: bool
    adapter_blocker: str
    held_out_case_count: int = 0
    public_extended_case_count: int = 0
    objective: str | None = None
    fixture_sets: tuple[str, ...] = ()
    task_output_key: str | None = None


def _manifest_paths():
    return sorted(_EXTENSIONS.glob('*/fixtures/manifest.json'))


@lru_cache(maxsize=None)
def _manifest(stem):
    path = _EXTENSIONS / stem / 'fixtures' / 'manifest.json'
    spec = json.loads(path.read_text('utf-8'))
    keys = {'schema', 'capsule_name', 'task_output_key', 'scope', 'sets'}
    if (not isinstance(spec, dict) or set(spec) != keys or spec['schema'] != FIXTURE_SCHEMA
            or not stem.isidentifier() or not isinstance(spec['capsule_name'], str)
            or not isinstance(spec['task_output_key'], str) or not isinstance(spec['scope'], str)
            or not isinstance(spec['sets'], dict) or set(spec['sets']) != set(FIXTURE_SETS)
            or any(not isinstance(v, str) or '/' in v or not v.endswith('.json') for v in spec['sets'].values())):
        raise ValueError('Invalid capsule fixture manifest: ' + stem)
    return spec


def _expand(node, env):
    """Tiny closed template language so large fixtures stay small data.

    ``{"$list": {"n", "var", "item"}}`` list; ``{"$join": {"sep", "items"}}``
    string join; ``{"$concat": [..]}`` list/string concatenation;
    ``{"$fmt": "..{var}.."}`` str.format over loop variables;
    ``{"$int": {"terms": {var: coef}, "add", "mod"}}`` integer arithmetic;
    ``{"$str": T}`` str(); ``{"$literal": T}`` no expansion.
    """
    if isinstance(node, list):
        return [_expand(item, env) for item in node]
    if not isinstance(node, dict):
        return node
    special = [key for key in node if key.startswith('$')]
    if not special:
        return {key: _expand(value, env) for key, value in node.items()}
    if len(node) != 1:
        raise ValueError('Template operators must be single-key objects')
    op, arg = next(iter(node.items()))
    if op == '$literal':
        return copy.deepcopy(arg)
    if op == '$list':
        if set(arg) != {'n', 'var', 'item'} or type(arg['n']) is not int or not 0 <= arg['n'] <= 100000:
            raise ValueError('Bounded $list required')
        return [_expand(arg['item'], {**env, arg['var']: index}) for index in range(arg['n'])]
    if op == '$join':
        items = _expand(arg['items'], env)
        if set(arg) != {'sep', 'items'} or any(type(item) is not str for item in items):
            raise ValueError('$join requires strings')
        return arg['sep'].join(items)
    if op == '$concat':
        parts = [_expand(item, env) for item in arg]
        if all(type(p) is str for p in parts):
            return ''.join(parts)
        if all(type(p) is list for p in parts):
            return [x for p in parts for x in p]
        raise ValueError('$concat requires all strings or all lists')
    if op == '$fmt':
        return arg.format(**env)
    if op == '$int':
        value = sum(coef * env[var] for var, coef in arg.get('terms', {}).items()) + arg.get('add', 0)
        return value % arg['mod'] if arg.get('mod') else value
    if op == '$str':
        return str(_expand(arg, env))
    raise ValueError('Unknown fixture template operator ' + op)


def _packet(data, files=(), envelope=None):
    envelope = envelope or {'provenance_id': 'public:synthetic-input',
        'limitations': ['Public synthetic fixture; no private or held-out evidence.']}
    return {'schema_version': '1.0.0', 'data': data,
        'files': [{'path': path, 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
                  for path, text in files], 'trust': 'low',
        'provenance': [{'id': envelope['provenance_id'], 'sha256': '0' * 64}],
        'limitations': list(envelope['limitations'])}


@lru_cache(maxsize=None)
def _raw_set(stem, fixture_set):
    spec = _manifest(stem)
    raw = json.loads((_EXTENSIONS / stem / 'fixtures' / spec['sets'][fixture_set]).read_text('utf-8'))
    if (not isinstance(raw, dict) or raw.get('schema') != FIXTURE_SET_SCHEMA or raw.get('fixture_set') != fixture_set
            or not set(raw) <= {'schema', 'fixture_set', 'envelope', 'defaults', 'cases', 'notes'}
            or not isinstance(raw.get('cases'), list)):
        raise ValueError('Invalid capsule fixture set: ' + stem + '/' + fixture_set)
    ids = [case.get('id') if isinstance(case, dict) else None for case in raw['cases']]
    if (any(not isinstance(ident, str) or not ident for ident in ids) or len(set(ids)) != len(ids)
            or any(not set(case) <= {'id', 'data', 'files', 'expected_task_output', 'note'} for case in raw['cases'])):
        raise ValueError('Invalid or duplicate fixture case: ' + stem + '/' + fixture_set)
    return raw


@lru_cache(maxsize=None)
def _fixture_set(stem, fixture_set):
    raw = _raw_set(stem, fixture_set)
    defaults = raw.get('defaults', {})
    cases = []
    for case in raw['cases']:
        data = _expand(case['data'], {})
        data.update({k: _expand(v, {}) for k, v in defaults.get('data', {}).items() if k not in data})
        files = [tuple(_expand(pair, {})) for pair in [*case.get('files', []), *defaults.get('files', [])]]
        cases.append({'id': case['id'], 'packet': _packet(data, files, raw.get('envelope')),
            'expected_task_output': _expand(case['expected_task_output'], {})})
    # Serialized once; every call returns fresh, independent objects.
    return json.dumps(cases, ensure_ascii=False)


def _discover():
    found = {}
    for path in _manifest_paths():
        stem = path.parent.parent.name
        spec = _manifest(stem)
        name = spec['capsule_name']
        if name in found:
            raise ValueError('Duplicate capsule fixture manifest identity')
        counts = {key: len(_raw_set(stem, key)['cases']) for key in FIXTURE_SETS}  # no expansion at import
        all_ids = [case['id'] for key in FIXTURE_SETS for case in _raw_set(stem, key)['cases']]
        if len(set(all_ids)) != len(all_ids):
            raise ValueError('Fixture ids must be unique across all sets of a capsule')
        found[name] = (stem, CapsuleTarget(name, f'research/capsule_extensions/{stem}/worker.py',
            f'research/capsule_extensions/{stem}/checks.py', spec['scope'],
            ('task_success', 'carrier_wall_s', 'output_bytes'), True,
            'Governed whole-capsule closure and separate development mutation declaration/grant required',
            held_out_case_count=counts['held_out'], public_extended_case_count=counts['public_extended'],
            objective=OBJECTIVE, fixture_sets=FIXTURE_SETS, task_output_key=spec['task_output_key']))
    return found


_DISCOVERED = _discover()
_STEMS = MappingProxyType({name: stem for name, (stem, _) in _DISCOVERED.items()})
_TARGETS = MappingProxyType({name: target for name, (_, target) in _DISCOVERED.items()} | {
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
        row['fixture_sets'] = list(target.fixture_sets)
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


def fixture_set(name, fixture_set):
    """Fresh fixtures of one named set: rows of id, packet, expected_task_output."""
    target = registered_capsule(name)
    if not target.public_evaluation_available:
        raise ValueError(target.adapter_blocker)
    if fixture_set not in FIXTURE_SETS:
        raise ValueError('Unknown fixture set')
    return json.loads(_fixture_set(_STEMS[name], fixture_set))


def public_fixtures(name):
    """Fresh fixtures and literal expected task outputs; all labels are public."""
    return fixture_set(name, 'public')


def _carrier(name):
    # Installed modules of the registered target only: neither fixture nor
    # caller selects a module; the stem is the discovered package directory.
    target = registered_capsule(name)
    if not target.public_evaluation_available:
        raise ValueError(target.adapter_blocker)
    stem = _STEMS[name]
    execute = importlib.import_module(f'{_PACKAGE}.{stem}.worker').execute
    check = importlib.import_module(f'{_PACKAGE}.{stem}.checks').check
    return execute, check, target.task_output_key


def _checked(check, before, output):
    checks = check(SimpleNamespace(output_refs={}), {'packet': before}, {'result': output})
    exact = (len(checks) == 2 and {r['check_id'] for r in checks} == {'packet_schema', 'packet_integrity'}
             and all(r['outcome'] == 'PASS' for r in checks))
    return checks, exact


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
        checks, exact_checks = _checked(check, before, output)
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


async def evaluate_in_process(name, *, role='parent', execute=None, fixture_sets=FIXTURE_SETS,
                              trials=1, iteration=0, capture_public_output=True):
    """Unsandboxed development evaluation producing an Interface A shaped result.

    Runs ``execute`` (default: the installed parent carrier) in this process
    over the named fixture sets, checked by the installed independent checker.
    It is for tests and local development only -- never governed evidence. Held
    out rows never carry actual outputs; public rows carry a bounded
    ``actual_task_output`` so score feedback can show a diff.
    """
    if type(trials) is not int or not 1 <= trials <= 50:
        raise ValueError('Bounded trial count required')
    default_execute, check, output_key = _carrier(name)
    execute = execute or default_execute
    cases = [(key, fixture) for key in fixture_sets for fixture in fixture_set(name, key)]
    rows, totals, failure = [], [], None
    if cases:  # Untimed warm-up so lazy imports are not charged to the first case.
        try:
            await execute(None, {'packet': copy.deepcopy(cases[0][1]['packet'])})
        except Exception:
            pass
    for trial in range(trials):
        total = 0.0
        for index, (key, fixture) in enumerate(cases):
            packet = fixture['packet']; before = copy.deepcopy(packet)
            started = perf_counter()
            raw, error = None, None
            try:
                raw = (await execute(None, {'packet': packet}))['result'].data
            except Exception as exc:  # A failing candidate is a scored outcome.
                error = {'exception_type': type(exc).__name__, 'message': str(exc)[:300]}
            elapsed = perf_counter() - started
            total += elapsed
            if trial:
                rows[index]['trial_wall_s'].append(elapsed)
                continue
            output, checks, ok = None, [], False
            if isinstance(raw, bytes):
                try:
                    output = json.loads(raw)
                    checks, ok = _checked(check, before, output)
                except ValueError as exc:
                    error = error or {'exception_type': type(exc).__name__, 'message': str(exc)[:300]}
            row = {'fixture_id': fixture['id'], 'fixture_set': 'held_out' if key == 'held_out' else 'public',
                'fixture_group': key, 'task_success': bool(ok and packet == before),
                'protected_wall_s': elapsed, 'trial_wall_s': [elapsed],
                'output_bytes': len(raw) if isinstance(raw, bytes) else 0,
                'checks': {r['check_id']: r['outcome'] for r in checks}, 'receipt': None, 'error': error}
            if capture_public_output and key != 'held_out' and isinstance(output, dict):
                data = output.get('data')
                actual = data.get(output_key) if isinstance(data, dict) else None
                if len(json.dumps(actual, ensure_ascii=False)) <= MAX_CAPTURED_OUTPUT_CHARS:
                    row['actual_task_output'] = actual
            rows.append(row)
        totals.append(total)
    return {'schema': 'ai4r-rsi-whole-capsule-visible-result:2', 'capsule_name': name,
        'role': role, 'iteration': iteration, 'subject_sha256': None,
        'passed_count': sum(row['task_success'] for row in rows), 'case_count': len(rows),
        'protected_wall_s': totals[0], 'trial_wall_s': totals, 'rows': rows,
        'executions': len(rows) * trials, 'failure': failure, 'governed_execution': False}
