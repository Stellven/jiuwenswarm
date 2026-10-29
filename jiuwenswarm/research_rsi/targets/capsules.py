"""Finite public evaluations of real capsule carriers, without execution grants.

These source candidates are distinct from the governed single-function helper
registry. Public synthetic fixtures are not held-out evidence or admission.

Packet capsule targets are discovered from data: an installed
``research/capsule_extensions/<stem>/fixtures/manifest.json`` registers the
capsule's fixture adapter. The product catalog selects its exact release,
declared worker carrier, independent checker and frozen dependencies. No capsule name is special-cased here.

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
    benchmark_workload_count: int = 0
    semantic_edge_case_count: int = 0
    release_module: str | None = None
    version_label: str | None = None
    selected_worker_module: str | None = None
    checks_module: str | None = None
    check_ids: tuple[str, ...] = ()
    release_manifest_sha256: str | None = None
    dependency_pins: tuple[tuple[str, str], ...] = ()
    checks_sha256: str | None = None
    declaration_sha256: str | None = None
    input_name: str = 'packet'
    required_services: tuple[str, ...] = ()


BENCHMARK_FILE = 'benchmark.json'
SEMANTIC_EDGES_FILE = 'semantic_edges.json'


def _manifest_paths():
    return sorted(_EXTENSIONS.glob('*/fixtures/manifest.json'))


@lru_cache(maxsize=None)
def _manifest(stem):
    path = _EXTENSIONS / stem / 'fixtures' / 'manifest.json'
    spec = json.loads(path.read_text('utf-8'))
    keys = {'schema', 'capsule_name', 'task_output_key', 'scope', 'sets'}
    for optional in ('release_module', 'input_name'):
        if optional in spec:
            keys.add(optional)
    if (not isinstance(spec, dict) or set(spec) != keys or spec['schema'] != FIXTURE_SCHEMA
            or not stem.isidentifier() or not isinstance(spec['capsule_name'], str)
            or not isinstance(spec.get('input_name', 'packet'), str)
            or not spec.get('input_name', 'packet').isidentifier()
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
    ``{"$str": T}`` str(); ``{"$literal": T}`` no expansion;
    ``{"$var": name}`` a copy of a bound variable's value (any JSON type);
    ``{"$slice": {"of", "start", "stop", "step"}}`` Python list/str slicing.
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
    if op == '$var':
        if not isinstance(arg, str) or arg not in env:
            raise ValueError('Unbound fixture template variable')
        return copy.deepcopy(env[arg])
    if op == '$slice':
        if not isinstance(arg, dict) or not {'of'} <= set(arg) <= {'of', 'start', 'stop', 'step'}:
            raise ValueError('$slice requires of/start/stop/step')
        value = _expand(arg['of'], env)
        bounds = [_expand(arg.get(key), env) for key in ('start', 'stop', 'step')]
        if not isinstance(value, (list, str)) or any(b is not None and type(b) is not int for b in bounds) or bounds[2] == 0:
            raise ValueError('$slice requires a list/string and integer bounds')
        return value[slice(*bounds)]
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
        input_name = _manifest(stem).get('input_name', 'packet')
        if input_name != 'packet' and files:
            raise ValueError('Raw declared-input fixtures must embed their own source data')
        cases.append({'id': case['id'], 'packet': (_packet(data, files, raw.get('envelope'))
                     if input_name == 'packet' else data),
            'expected_task_output': _expand(case['expected_task_output'], {})})
    # Serialized once; every call returns fresh, independent objects.
    return json.dumps(cases, ensure_ascii=False)


class _SourceStore:
    """Content addressed, memory-only asset preparation; no Core/library effects."""
    def __init__(self):
        self.records = {}
    def put_blob(self, raw, **kwargs):
        return {'id': 'blob:' + hashlib.sha256(raw).hexdigest(), 'sha256': hashlib.sha256(raw).hexdigest()}
    def put_record(self, contract_id, value):
        ref = self.put_blob(encoded(value))
        self.records[ref['id']] = value
        return ref
    def read_record(self, ref, **kwargs):
        return self.records[ref['id']]


@lru_cache(maxsize=None)
def _release_binding(name):
    """Resolve the product-selected release and validate its complete source pins."""
    matches = []
    for path in sorted(_EXTENSIONS.glob('*/release.json')):
        spec = json.loads(path.read_text('utf-8'))
        if spec.get('name') == name:
            matches.append((path, spec))
    if len(matches) != 1:
        raise ValueError('Exactly one selected release required: ' + name)
    path, spec = matches[0]
    module = spec['module']
    if not isinstance(module, str) or not module.isidentifier() or path.parent.name != module:
        raise ValueError('Invalid selected release module')
    required = {source.relative_to(_EXTENSIONS).as_posix() for source in path.parent.glob('*.py')}
    if 'shared_runtime' not in spec:
        required |= {'assets.py', 'packet.py'}
    if set(spec['files']) != required:
        raise ValueError('Incomplete selected release source closure')
    pins = dict(spec['files'])
    pins.update({row['path']: row['sha256'] for row in spec.get('shared_dependencies', [])})
    if 'shared_runtime' in spec:
        pins[spec['shared_runtime']['path']] = spec['shared_runtime']['sha256']
    for relative, digest in pins.items():
        source = (_EXTENSIONS / relative).resolve()
        if not source.is_relative_to(_EXTENSIONS.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError('Selected release source pin differs: ' + relative)
    store = _SourceStore()
    release = importlib.import_module(f'{_PACKAGE}.{module}.release')
    asset = release.prepare(store)
    declaration = store.read_record(asset['declaration_ref'])
    for body_path, ref in asset['body_refs'].items():
        relative = body_path.removeprefix('capsule_extensions/')
        if pins.get(relative) != ref['sha256']:
            raise ValueError('Selected declaration body/dependency differs from release manifest: ' + body_path)
    identity = declaration['identity']
    if identity['name'] != name:
        raise ValueError('Selected declaration identity differs')
    carrier = 'research/' + identity['carrier']['ref']
    worker_module = 'jiuwenswarm.' + carrier.removesuffix('.py').replace('/', '.')
    checks_module = f'{_PACKAGE}.{module}.checks'
    checks_path = checks_module.removeprefix('jiuwenswarm.').replace('.', '/') + '.py'
    inputs = declaration['ports']['inputs']
    input_name = inputs[0]['name'] if len(inputs) == 1 else None
    return {'release_module': module, 'version_label': identity['version_label'], 'input_name': input_name,
        'required_services': tuple(sorted(row['service_key'] for row in declaration['needs']['injects'])),
        'carrier_path': carrier, 'checks_path': checks_path, 'selected_worker_module': worker_module,
        'checks_module': checks_module, 'check_ids': tuple(declaration['guarantees']['acceptance']),
        'release_manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'declaration_sha256': asset['declaration_ref']['sha256'],
        'dependency_pins': tuple(sorted(('research/capsule_extensions/' + key, digest) for key, digest in pins.items())),
        'checks_sha256': hashlib.sha256((_EXTENSIONS / module / 'checks.py').read_bytes()).hexdigest()}


def release_binding(name):
    # Callers receive detached facts; mutating a captured manifest cannot
    # change the authoritative installed-release cache used to validate it.
    binding = _release_binding(name)
    path = _EXTENSIONS / binding['release_module'] / 'release.json'
    if hashlib.sha256(path.read_bytes()).hexdigest() != binding['release_manifest_sha256']:
        raise ValueError('Selected release manifest changed')
    return copy.deepcopy(binding)


def runtime_target_bindings():
    return {name: release_binding(name) for name, target in _TARGETS.items() if target.public_evaluation_available}


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
        extras = {key: _optional_spec(stem, file) for key, file in (('benchmark', BENCHMARK_FILE),
                                                                    ('semantic', SEMANTIC_EDGES_FILE))}
        for extra in extras.values():
            if extra is not None and extra.get('capsule_name') != name:
                raise ValueError('Capsule spec names a different capsule: ' + stem)
        binding = release_binding(name)
        fixture_current = (spec.get('release_module', binding['release_module']) == binding['release_module']
                           and spec.get('input_name', 'packet') == binding['input_name'])
        found[name] = (stem, CapsuleTarget(name, binding['carrier_path'],
            binding['checks_path'], spec['scope'],
            ('task_success', 'carrier_wall_s', 'output_bytes'), fixture_current,
            ('Governed whole-capsule closure and separate development mutation declaration/grant required'
             if fixture_current else 'Fixture manifest is stale for the selected release; regenerate through its checker'),
            held_out_case_count=counts['held_out'], public_extended_case_count=counts['public_extended'],
            objective=OBJECTIVE, fixture_sets=FIXTURE_SETS, task_output_key=spec['task_output_key'],
            benchmark_workload_count=len((extras['benchmark'] or {}).get('workloads', ())),
            semantic_edge_case_count=len((extras['semantic'] or {}).get('cases', ())),
            **{key: binding[key] for key in ('release_module', 'version_label', 'selected_worker_module',
                'checks_module', 'check_ids', 'release_manifest_sha256', 'dependency_pins', 'checks_sha256', 'declaration_sha256', 'input_name', 'required_services')}))
    for path in sorted(_EXTENSIONS.glob('*/release.json')):
        spec = json.loads(path.read_text('utf-8'))
        name = spec['name']
        if name not in found:
            b = release_binding(name)
            found[name] = (None, CapsuleTarget(name, b['carrier_path'], b['checks_path'],
                'selected release without a packet fixture adapter', ('task_success',), False,
                ('Selected release requires governed invocation context and declared services: ' + ', '.join(b['required_services'])
                 + '; model-free execution is unavailable' if b['required_services']
                 else 'Selected release has no compatible RSI fixture manifest'),
                **{key: b[key] for key in ('release_module', 'version_label', 'selected_worker_module',
                    'checks_module', 'check_ids', 'release_manifest_sha256', 'dependency_pins', 'checks_sha256', 'declaration_sha256', 'input_name', 'required_services')}))
    return found


@lru_cache(maxsize=None)
def _optional_spec_text(stem, file):
    path = _EXTENSIONS / stem / 'fixtures' / file
    return path.read_text('utf-8') if path.is_file() else None


def _optional_spec(stem, file):
    """Fresh parsed optional per-capsule spec (benchmark / semantic edges) or None."""
    text = _optional_spec_text(stem, file)
    value = None if text is None else json.loads(text)
    if value is not None and not isinstance(value, dict):
        raise ValueError('Capsule spec must be an object: ' + stem + '/' + file)
    return value


_DISCOVERED = _discover()
_STEMS = MappingProxyType({name: stem for name, (stem, _) in _DISCOVERED.items() if stem is not None})
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
        row['check_ids'] = list(target.check_ids)
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


def benchmark_spec(name):
    """The capsule's ``fixtures/benchmark.json`` workload spec, or None (fresh copy)."""
    registered_capsule(name)
    return _optional_spec(_STEMS[name], BENCHMARK_FILE) if name in _STEMS else None


def semantic_edges_spec(name):
    """The capsule's ``fixtures/semantic_edges.json`` spec, or None (fresh copy)."""
    registered_capsule(name)
    return _optional_spec(_STEMS[name], SEMANTIC_EDGES_FILE) if name in _STEMS else None


def carrier_module(name):
    """Dotted module name of the registered capsule's worker carrier."""
    registered_capsule(name)
    if name not in _STEMS:
        raise ValueError('No packet carrier module for target')
    return registered_capsule(name).selected_worker_module


def fixture_inputs(name, fixture):
    """Bind a fixture's source value to the selected declaration's input port."""
    target = registered_capsule(name)
    if not isinstance(target.input_name, str) or not target.input_name.isidentifier():
        raise ValueError('One declared input port is required for this fixture adapter')
    return {target.input_name: fixture['packet']}


def public_fixtures(name):
    """Fresh fixtures and literal expected task outputs; all labels are public."""
    return fixture_set(name, 'public')


def _carrier(name):
    # Installed modules of the registered target only: neither fixture nor
    # caller selects a module; the stem is the discovered package directory.
    target = registered_capsule(name)
    if not target.public_evaluation_available:
        raise ValueError(target.adapter_blocker)
    execute = importlib.import_module(target.selected_worker_module).execute
    check = importlib.import_module(target.checks_module).check
    return execute, check, target.task_output_key


def _checked(check, before, output, check_ids, *, input_name='packet'):
    checks = check(SimpleNamespace(output_refs={}), {input_name: before}, {'result': output})
    exact = (len(checks) == len(check_ids) and {r['check_id'] for r in checks} == set(check_ids)
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
                for path, _ in target.dependency_pins}
    rows = []
    for fixture in public_fixtures(name):
        packet = fixture['packet']; before = copy.deepcopy(packet)
        started = perf_counter()
        artifact = (await execute(None, fixture_inputs(name, {'packet': packet})))['result']
        elapsed = perf_counter() - started
        raw = artifact.data
        if not isinstance(raw, bytes):
            raise ValueError('Actual capsule must produce serialized packet bytes')
        output = json.loads(raw)
        checks, exact_checks = _checked(check, before, output, registered_capsule(name).check_ids,
                                        input_name=registered_capsule(name).input_name)
        expected_packet = copy.deepcopy(output)
        expected_packet['data'][output_key] = fixture['expected_task_output']
        preserved = packet == before and exact_checks
        task_matches = encoded(output.get('data', {}).get(output_key)) == encoded(fixture['expected_task_output'])
        rows.append({'fixture_id': fixture['id'], 'input_sha256': hashlib.sha256(encoded(before)).hexdigest(),
            'expected_sha256': hashlib.sha256(encoded(expected_packet)).hexdigest(),
            'task_success': bool(exact_checks and preserved and task_matches), 'input_unmodified': packet == before,
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
            await execute(None, fixture_inputs(name, {'packet': copy.deepcopy(cases[0][1]['packet'])}))
        except Exception:
            pass
    for trial in range(trials):
        total = 0.0
        for index, (key, fixture) in enumerate(cases):
            packet = fixture['packet']; before = copy.deepcopy(packet)
            started = perf_counter()
            raw, error = None, None
            try:
                raw = (await execute(None, fixture_inputs(name, {'packet': packet})))['result'].data
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
                    checks, ok = _checked(check, before, output, registered_capsule(name).check_ids,
                                        input_name=registered_capsule(name).input_name)
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
