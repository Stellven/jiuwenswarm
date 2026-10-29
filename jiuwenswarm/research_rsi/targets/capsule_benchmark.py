"""Paired, batched, CI-gated capsule benchmark: workloads, protocol, statistics.

Ported from Codex's ``capsule_benchmark.py`` (the judge behind its measured
Calculate/Normalize gains) with two changes:

* **Data-driven workloads.** Every workload comes from the capsule's
  ``capsule_extensions/<stem>/fixtures/benchmark.json`` (found by the catalog):
  generated synthetic tables, cases derived from an earlier case by setting
  packet paths, and literal packets. One generic generator serves every
  capsule; no capsule name is branched on. Current specs follow each selected release's contract. Historical frozen
  records retain their original protocols and are replayed independently.
* **Correctness contract.** The authority-side checker decides correctness.
  Where the parent passes the checker on a case the candidate must reproduce
  the parent's output bytes exactly; where the parent fails it, a candidate
  that passes the checker (an improvement) or reproduces the parent exactly
  (no regression) is accepted. Malformed cases require the
  parent's exact error identity (type, code, message) when the parent raised.
  The trusted runtime guard must report the input unchanged in every case.

Timing is the per-process wall of a protected (or explicitly local) job divided
by its fixed batch size; parent and candidate alternate AB/BA per repetition.
The aggregate is the equal-weight geometric mean of per-workload median
candidate/parent ratios with a seeded paired bootstrap confidence interval.
Only installed parent code ever runs in this process (``parent_expectations``).
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
import random
import statistics
from functools import lru_cache
from types import SimpleNamespace

from ..records import encoded
from .capsules import _expand, _packet, benchmark_spec, registered_capsule

SPEC_SCHEMA = 'ai4r-rsi-capsule-benchmark-workloads:1'
PROTOCOL_SCHEMA = 'ai4r-rsi-capsule-benchmark:2'
REPORT_SCHEMA = 'ai4r-rsi-capsule-benchmark-report:1'
COMPARISON_SCHEMA = 'ai4r-rsi-capsule-performance-comparison:1'
DEFAULT_GATES = {'minimum_gain': 0.10, 'ci_upper_bound': 0.90, 'max_workload_regression': 0.05}
DEFAULT_REPETITIONS = 11
DEFAULT_BOOTSTRAP_SEED = 20261026
CORRECTNESS_CONTRACT = ('checker authoritative; exact parent output bytes where the parent passes the checker; '
                        'where the parent fails it, a checker pass (improvement) or the exact parent behaviour '
                        '(no regression); exact parent error identity on malformed cases; input unchanged '
                        '(trusted runtime guard)')
_CASE_KEYS = {'id', 'timed', 'batch', 'table', 'vars', 'malformed', 'derive', 'set', 'data', 'files',
              'since_version', 'note'}
_SPEC_KEYS = {'schema', 'capsule_name', 'notes', 'protocol', 'statistics', 'withheld_splits',
              'table_defaults', 'workload_packet', 'splits', 'workloads', 'input_name'}
_MAX_CELLS = 2_000_000


def need(condition, message):
    if not condition:
        raise ValueError(message)


# --------------------------------------------------------------- workload data

def _spec(name):
    spec = benchmark_spec(name)
    need(spec is None or spec.get('input_name', 'packet') == registered_capsule(name).input_name, 'BENCHMARK_INPUT_DIFFERS_FROM_SELECTED_DECLARATION')
    need(spec is not None, 'NO_BENCHMARK_SPEC_FOR_TARGET')
    need(set(spec) <= _SPEC_KEYS and {'schema', 'capsule_name', 'protocol', 'splits'} <= set(spec)
         and spec['schema'] == SPEC_SCHEMA and spec['capsule_name'] == name
         and isinstance(spec['splits'], dict) and spec['splits']
         and all(isinstance(rows, list) and rows for rows in spec['splits'].values())
         and set(spec.get('withheld_splits', ())) <= set(spec['splits']), 'CLOSED_BENCHMARK_SPEC_REQUIRED')
    # ``workloads``: the timed workload ids in order (an index other tools size from).
    timed = [row['id'] for rows in spec['splits'].values() for row in rows if row.get('timed') is True]
    need(spec.get('workloads', timed) == timed, 'BENCHMARK_WORKLOAD_INDEX_DIFFERS')
    protocol = spec['protocol']
    need(isinstance(protocol, dict) and {'batch_iterations', 'repetitions', 'warmups'} <= set(protocol)
         and not {'schema', 'capsule_name', 'splits'} & set(protocol), 'CLOSED_BENCHMARK_PROTOCOL_REQUIRED')
    return spec


def _table(spec):
    """Synthetic table: cell (i, k) = ((row_coef*i + col_coef*j + add) % mod + offset) / divisor
    with j = k (``forward``) or width-1-k (``reversed``); optional format, patches, encoding."""
    need(isinstance(spec, dict) and set(spec) <= {'height', 'width', 'column_name', 'cell', 'format', 'patches', 'encoding'},
         'CLOSED_TABLE_SPEC_REQUIRED')
    height, width, cell = spec['height'], spec['width'], spec['cell']
    need(type(height) is int and type(width) is int and 0 <= height and 0 < width and height * width <= _MAX_CELLS,
         'BOUNDED_TABLE_REQUIRED')
    need(set(cell) <= {'row_coef', 'col_coef', 'col_index', 'add', 'mod', 'offset', 'divisor'}
         and cell.get('col_index', 'forward') in ('forward', 'reversed') and type(cell['mod']) is int and cell['mod'] > 0,
         'CLOSED_TABLE_CELL_REQUIRED')
    columns = [spec['column_name'].format(k=k) for k in range(width)]
    reverse = cell.get('col_index') == 'reversed'
    row_coef, col_coef = cell.get('row_coef', 0), cell.get('col_coef', 0)
    add, mod, offset, divisor = cell.get('add', 0), cell['mod'], cell.get('offset', 0), cell.get('divisor')
    fmt = spec.get('format')

    def value(i, k):
        j = width - 1 - k if reverse else k
        number = (row_coef * i + col_coef * j + add) % mod + offset
        if divisor:
            number = number / divisor
        return format(number, fmt) if fmt else number
    matrix = [[value(i, k) for k in range(width)] for i in range(height)]
    for patch in spec.get('patches', ()):
        need(isinstance(patch, dict) and 'rows' in patch and (set(patch) == {'rows', 'row_values'}
             or set(patch) == {'rows', 'column', 'value'}), 'CLOSED_TABLE_PATCH_REQUIRED')
        rows = patch['rows']
        if isinstance(rows, dict):
            need(set(rows) <= {'start', 'step'} and type(rows.get('step', 1)) is int and rows.get('step', 1) > 0,
                 'BOUNDED_PATCH_ROW_RANGE_REQUIRED')
            rows = range(rows.get('start', 0), height, rows.get('step', 1))
        for i in rows:
            if 'row_values' in patch:
                matrix[i] = copy.deepcopy(patch['row_values'])
            else:
                matrix[i][patch['column']] = copy.deepcopy(patch['value'])
    encoding = spec.get('encoding', {'kind': 'rows'})
    kind = encoding.get('kind')
    if kind == 'rows':
        need(set(encoding) == {'kind'}, 'CLOSED_TABLE_ENCODING_REQUIRED')
        table = matrix
    elif kind == 'records_json':
        need(set(encoding) <= {'kind', 'key_order'} and encoding.get('key_order', 'forward') in ('forward', 'reversed'),
             'CLOSED_TABLE_ENCODING_REQUIRED')
        order = list(range(width))[::-1] if encoding.get('key_order') == 'reversed' else list(range(width))
        table = json.dumps([{columns[k]: row[k] for k in order} for row in matrix],
                           ensure_ascii=False, separators=(',', ':'))
    elif kind == 'csv':
        need(set(encoding) <= {'kind', 'delimiter', 'lineterminator'}, 'CLOSED_TABLE_ENCODING_REQUIRED')
        stream = io.StringIO(newline='')
        writer = csv.writer(stream, delimiter=encoding.get('delimiter', ','),
                            lineterminator=encoding.get('lineterminator', '\r\n'))
        writer.writerow(columns)
        for row in matrix:
            writer.writerow(row)
        table = stream.getvalue()
    else:
        raise ValueError('KNOWN_TABLE_ENCODING_REQUIRED')
    return {'columns': columns, 'table': table}


def _set_path(packet, path, value):
    need(isinstance(path, list) and path, 'PACKET_PATH_REQUIRED')
    node = packet
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = copy.deepcopy(value)


def build_cases(rows, *, split, table_defaults=None, workload_packet=None, version=None, input_name='packet'):
    """Generic case builder shared by benchmark and semantic-edge specs.

    Each row is exactly one of: a generated workload (``table`` + the spec's
    ``workload_packet`` template), a derived case (``derive`` an earlier case
    id of the same list, then ``set`` packet paths), or a literal packet
    (``data`` + ``files`` templates). Returns Codex's fixture shape
    ``{id, split, packet, malformed}`` in row order.
    """
    built, cases = {}, []
    for row in rows:
        need(isinstance(row, dict) and set(row) <= _CASE_KEYS and isinstance(row.get('id'), str) and row['id']
             and row['id'] not in built, 'CLOSED_UNIQUE_BENCHMARK_CASE_REQUIRED')
        if version is not None and row.get('since_version', 1) > version:
            continue
        kinds = [key for key in ('table', 'derive', 'data') if key in row]
        need(len(kinds) == 1, 'EXACTLY_ONE_CASE_KIND_REQUIRED')
        env = dict(row.get('vars', {}))
        if kinds == ['table']:
            need(input_name == 'packet', 'TABLE_GENERATOR_REQUIRES_PACKET_INPUT')
            need(isinstance(workload_packet, dict) and set(workload_packet) <= {'data', 'files'},
                 'WORKLOAD_PACKET_TEMPLATE_REQUIRED')
            env.update(_table({**(table_defaults or {}), **row['table']}))
            data = _expand(workload_packet['data'], env)
            files = [tuple(_expand(pair, env)) for pair in workload_packet.get('files', ())]
            packet = _packet(data, files)
        elif kinds == ['derive']:
            need(row['derive'] in built, 'DERIVED_CASE_BASE_MUST_PRECEDE')
            packet = copy.deepcopy(built[row['derive']])
            for item in row.get('set', ()):
                need(isinstance(item, dict) and set(item) == {'path', 'value'}, 'CLOSED_PACKET_SET_REQUIRED')
                _set_path(packet, item['path'], item['value'])
        else:
            data = _expand(row['data'], env)
            files = [tuple(_expand(pair, env)) for pair in row.get('files', ())]
            need(input_name == 'packet' or not files, 'NONPACKET_FIXTURE_FILES_MUST_BE_IN_DECLARED_INPUT')
            packet = _packet(data, files) if input_name == 'packet' else data
        built[row['id']] = packet
        cases.append({'id': row['id'], 'split': split, 'packet': packet, 'malformed': row.get('malformed', False) is True})
    return cases


@lru_cache(maxsize=None)
def _fixtures_text(name):
    spec = _spec(name)
    value = {split: build_cases(rows, split=split, table_defaults=spec.get('table_defaults'),
                                workload_packet=spec.get('workload_packet'), input_name=spec.get('input_name', 'packet'))
             for split, rows in spec['splits'].items()}
    return json.dumps(value, ensure_ascii=False)


@lru_cache(maxsize=None)
def _timing_text(name):
    spec = _spec(name)
    batches = spec['protocol']['batch_iterations']
    timing = {}
    for split, rows in spec['splits'].items():
        for row in rows:
            if row.get('timed') is True:
                need(row.get('malformed', False) is False and row.get('batch') in batches and row['id'] not in timing,
                     'UNIQUE_TIMED_VALID_BATCHED_CASE_REQUIRED')
                timing[row['id']] = row['batch']
            else:
                need('batch' not in row, 'UNTIMED_CASE_HAS_NO_BATCH')
    return json.dumps(timing)


def benchmark_splits(name):
    return list(_spec(name)['splits'])


def withheld_splits(name):
    return list(_spec(name).get('withheld_splits', ()))


def benchmark_fixtures(name, split='visible'):
    """Fresh cases of one split (Codex shape ``{id, split, packet, malformed}``)."""
    registered_capsule(name)
    value = json.loads(_fixtures_text(name))
    if split not in value:
        raise ValueError('Unknown benchmark split')
    return value[split]


def all_benchmark_fixtures(name):
    return [case for split in benchmark_splits(name) for case in benchmark_fixtures(name, split)]


def timing_batches(name):
    """``{workload id: batch class}`` for every timed workload."""
    return json.loads(_timing_text(name))


def benchmark_protocol(name):
    """The frozen protocol exactly as the spec defines it (Codex schema :2)."""
    spec = _spec(name)
    timing = timing_batches(name)
    splits = {}
    for split in benchmark_splits(name):
        fixtures = benchmark_fixtures(name, split)
        splits[split] = {'sha256': hashlib.sha256(encoded(fixtures)).hexdigest(), 'case_count': len(fixtures),
                         'timing_case_ids': [case['id'] for case in fixtures if case['id'] in timing]}
    return {'schema': PROTOCOL_SCHEMA, 'capsule_name': name, 'splits': splits, **copy.deepcopy(spec['protocol'])}


# ------------------------------------------------------------- configuration

def benchmark_config(name, overrides=None):
    """Effective benchmark configuration: spec defaults, then ``overrides``.

    Keys: repetitions, warmups, batch_iterations (per batch class), gates
    {minimum_gain, ci_upper_bound, max_workload_regression}, confidence,
    bootstrap_resamples, bootstrap_seed, semantic_edges (bool),
    semantic_version, max_benchmarks (loop budget only).
    """
    from .capsules import semantic_edges_spec
    spec = _spec(name)
    protocol = spec['protocol']
    minimum = protocol.get('minimum_relative_gain', DEFAULT_GATES['minimum_gain'])
    semantic = semantic_edges_spec(name)
    config = {'repetitions': protocol.get('repetitions', DEFAULT_REPETITIONS), 'warmups': protocol['warmups'],
        'batch_iterations': dict(protocol['batch_iterations']),
        'gates': {'minimum_gain': minimum, 'ci_upper_bound': 1 - minimum,
                  'max_workload_regression': protocol.get('regression_limit', DEFAULT_GATES['max_workload_regression'])},
        'confidence': protocol.get('confidence', 0.95), 'bootstrap_resamples': protocol.get('bootstrap_resamples', 5000),
        'bootstrap_seed': spec.get('statistics', {}).get('bootstrap_seed', DEFAULT_BOOTSTRAP_SEED),
        'semantic_edges': semantic is not None,
        'semantic_version': max([1, *(row.get('since_version', 1) for row in (semantic or {}).get('cases', ()))]),
        'max_benchmarks': None}
    overrides = dict(overrides or {})
    need(set(overrides) <= set(config), 'KNOWN_BENCHMARK_CONFIG_KEYS_REQUIRED')
    for key, value in overrides.items():
        if key == 'gates':
            need(isinstance(value, dict) and set(value) <= set(DEFAULT_GATES), 'KNOWN_BENCHMARK_GATES_REQUIRED')
            config['gates'].update(value)
        elif key == 'batch_iterations':
            need(isinstance(value, dict) and set(value) <= set(config['batch_iterations']), 'KNOWN_BATCH_CLASSES_REQUIRED')
            config['batch_iterations'].update(value)
        else:
            config[key] = value
    finite = lambda x, lo, hi: type(x) in (int, float) and math.isfinite(x) and lo <= x <= hi
    gates = config['gates']
    need(type(config['repetitions']) is int and 1 <= config['repetitions'] <= 101
         and type(config['warmups']) is int and 0 <= config['warmups'] <= 10
         and all(type(v) is int and 1 <= v <= 10000 for v in config['batch_iterations'].values())
         and finite(gates['minimum_gain'], -1, 1) and finite(gates['ci_upper_bound'], 0, 10)
         and finite(gates['max_workload_regression'], 0, 10)
         and finite(config['confidence'], 0.5, 0.999) and type(config['bootstrap_resamples']) is int
         and 100 <= config['bootstrap_resamples'] <= 100000 and type(config['bootstrap_seed']) is int
         and type(config['semantic_edges']) is bool and (semantic is not None or not config['semantic_edges'])
         and type(config['semantic_version']) is int and config['semantic_version'] >= 1
         and (config['max_benchmarks'] is None or type(config['max_benchmarks']) is int and config['max_benchmarks'] >= 0),
         'FINITE_BENCHMARK_CONFIG_REQUIRED')
    return config


def effective_protocol(name, config):
    """The frozen protocol with this configuration's parameters applied."""
    value = benchmark_protocol(name)
    value.update(repetitions=config['repetitions'], warmups=config['warmups'],
                 batch_iterations=dict(config['batch_iterations']), confidence=config['confidence'],
                 bootstrap_resamples=config['bootstrap_resamples'],
                 minimum_relative_gain=config['gates']['minimum_gain'],
                 regression_limit=config['gates']['max_workload_regression'])
    if not math.isclose(config['gates']['ci_upper_bound'], 1 - config['gates']['minimum_gain'], abs_tol=1e-12):
        value['ci_upper_bound'] = config['gates']['ci_upper_bound']
    return value


def execution_plan(name, config):
    """Ordered jobs: per case of every split, timed cases ``repetitions`` x
    (parent, candidate) alternating AB/BA, untimed cases once (AB)."""
    timing = timing_batches(name)
    jobs = []
    for fixture in all_benchmark_fixtures(name):
        timed = fixture['id'] in timing
        for repeat in range(config['repetitions'] if timed else 1):
            roles = ('parent', 'candidate') if repeat % 2 == 0 else ('candidate', 'parent')
            for role in roles:
                jobs.append({'fixture': fixture, 'timed': timed, 'repeat': repeat, 'role': role,
                             'batch_iterations': config['batch_iterations'][timing[fixture['id']]] if timed else 1,
                             'warmups': config['warmups'] if timed else 0})
    return jobs


def benchmark_job_count(name, config=None):
    """Executions one ``benchmark()`` call uses (paired jobs + semantic-edge jobs)."""
    config = benchmark_config(name, config)  # Idempotent on an effective configuration.
    timing = timing_batches(name)
    count = sum(2 * (config['repetitions'] if case['id'] in timing else 1) for case in all_benchmark_fixtures(name))
    if config['semantic_edges']:
        from .capsule_semantic_edges import semantic_edge_fixtures
        count += 2 * len(semantic_edge_fixtures(name, version=config['semantic_version']))
    return count


# -------------------------------------------------------- parent / correctness

def _drive(execute, packet, *, input_name='packet'):
    invocation = execute(None, {input_name: packet})
    try:
        invocation.send(None)
    except StopIteration as completed:
        return completed.value['result'].data
    else:
        invocation.close()
        raise ValueError('Pure carrier suspended')


def _error(error):
    return {'type': type(error).__name__, 'code': getattr(error, 'code', None), 'message': str(error)}


def parent_expectations(name, split, *, fixtures=None):
    """Exact installed-parent behaviour per case (Codex's frozen expectations).

    Records ``output_sha256`` (and whether the parent passes the checker) or
    the exact error; never imports candidate code.
    """
    from .capsules import _carrier
    execute, check, _ = _carrier(name)
    rows = []
    for fixture in fixtures if fixtures is not None else benchmark_fixtures(name, split):
        packet = fixture['packet']; before = copy.deepcopy(packet)
        try:
            raw = _drive(execute, packet, input_name=registered_capsule(name).input_name)
        except Exception as error:  # A parent error is recorded, not raised.
            row = {'id': fixture['id'], 'error': _error(error)}
        else:
            checked = check(SimpleNamespace(output_refs={}), {registered_capsule(name).input_name: before}, {'result': json.loads(raw)})
            row = {'id': fixture['id'], 'output_sha256': hashlib.sha256(raw).hexdigest(),
                   'checker_passed': (len(checked) == len(registered_capsule(name).check_ids)
                                      and {r['check_id'] for r in checked} == set(registered_capsule(name).check_ids)
                                      and all(r['outcome'] == 'PASS' for r in checked))}
        need(packet == before, 'INSTALLED_PARENT_MUTATED_INPUT')
        rows.append({**row, 'input_sha256': hashlib.sha256(encoded(before)).hexdigest()})
    return rows


def checker_passes(name, packet, output, *, expected_checks_sha256=None, binding=None):
    """The installed independent checker's verdict on captured output bytes."""
    from .capsule_runtime import check_capsule_output
    if not isinstance(output, bytes):
        return False
    try:
        return check_capsule_output(name, inputs={registered_capsule(name).input_name: packet}, output=output,
                                    expected_checks_sha256=expected_checks_sha256, **({'binding': binding} if binding is not None else {}))['task_success'] is True
    except (ValueError, TypeError, KeyError, UnicodeError):
        return False


def observation(*, completed, input_unmodified=False, output=None, error=None, detail=None):
    """A captured job outcome as the correctness judge reads it."""
    return {'completed': completed is True, 'input_unmodified': input_unmodified is True,
            'output': output, 'error': error, 'detail': detail}


def judge(name, fixture, parent, candidate, *, parent_checker_passed=None, expected_checks_sha256=None, binding=None):
    """Correctness of one candidate observation against the paired parent one.

    Returns ``{passed, rule, reason}``; ``rule`` is ``exact_parent_bytes``,
    ``checker``, ``error_identity`` or ``must_error``.
    """
    def verdict(passed, rule, reason=None):
        return {'passed': bool(passed), 'rule': rule, 'reason': None if passed else reason}
    if not parent['completed'] or not parent['input_unmodified']:
        return verdict(False, 'parent_reference', 'parent job failed or mutated its input')
    if not candidate['completed']:
        return verdict(False, 'job', 'candidate job failed: ' + str(candidate.get('detail') or 'no result')[:256])
    if not candidate['input_unmodified']:
        return verdict(False, 'input_guard', 'candidate mutated its input')
    if fixture['malformed']:
        if parent['error'] is not None:
            same = candidate['output'] is None and candidate['error'] == parent['error']
            return verdict(same, 'error_identity', 'error differs from the parent error identity (type, code, message)')
        return verdict(candidate['output'] is None and candidate['error'] is not None, 'must_error',
                       'malformed input must raise')
    if parent_checker_passed is None:
        parent_checker_passed = parent['error'] is None and checker_passes(
            name, fixture['packet'], parent['output'], expected_checks_sha256=expected_checks_sha256, binding=binding)
    if parent_checker_passed:
        same = candidate['error'] is None and candidate['output'] == parent['output']
        return verdict(same, 'exact_parent_bytes', 'output bytes differ from the parent (parent passes the checker)'
                       if candidate['error'] is None else 'raised where the parent succeeded')
    # The parent fails the checker here: the checker is authoritative. Passing
    # it is an improvement; reproducing the parent exactly is no regression.
    if candidate['error'] is None and checker_passes(name, fixture['packet'], candidate['output'],
                                                     expected_checks_sha256=expected_checks_sha256, binding=binding):
        return {**verdict(True, 'checker'), 'improved': True}
    unchanged = (candidate['output'], candidate['error']) == (parent['output'], parent['error'])
    return {**verdict(unchanged, 'checker', 'fails the independent checker and differs from the parent'),
            'improved': False}


# ----------------------------------------------------------------- statistics

def _percentile_index(count, fraction):
    return min(count - 1, max(0, int(round(count * fraction, 9))))


def compare_paired_samples(samples, *, workload_ids, gates=None, resamples=5000, seed=DEFAULT_BOOTSTRAP_SEED,
                           confidence=0.95, correctness_passed=True):
    """Gate one candidate on paired ``[parent_s, candidate_s]`` samples.

    Equal-weight geometric mean of per-workload median ratios; seeded paired
    bootstrap (resampling pairs within each workload) for the interval.
    """
    gates = {**DEFAULT_GATES, **(gates or {})}
    need(list(samples) == list(workload_ids) or set(samples) == set(workload_ids), 'EXACT_TIMING_INVENTORY_REQUIRED')
    need(workload_ids, 'TIMED_WORKLOADS_REQUIRED')
    for ident in workload_ids:
        pairs = samples[ident]
        need(isinstance(pairs, list) and pairs and all(
            isinstance(pair, (list, tuple)) and len(pair) == 2
            and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in pair) for pair in pairs),
            'FINITE_COMPLETE_PAIRED_SAMPLES_REQUIRED')
    rows, ratios = [], []
    for ident in workload_ids:
        median_ratio = statistics.median(child / parent for parent, child in samples[ident])
        ratios.append(median_ratio)
        rows.append({'id': ident, 'median_ratio': median_ratio, 'relative_gain': 1 - median_ratio,
                     'regression': median_ratio > 1})
    ratio = math.exp(statistics.mean(math.log(value) for value in ratios))
    rng = random.Random(seed)
    distribution = []
    for _ in range(resamples):
        boot = [statistics.median(child / parent for parent, child in rng.choices(samples[ident], k=len(samples[ident])))
                for ident in workload_ids]
        distribution.append(math.exp(statistics.mean(math.log(value) for value in boot)))
    distribution.sort()
    tail = (1 - confidence) / 2
    interval = [distribution[_percentile_index(len(distribution), tail)],
                distribution[_percentile_index(len(distribution), 1 - tail)]]
    results = {'correctness': correctness_passed is True,
               'minimum_gain': 1 - ratio >= gates['minimum_gain'],
               'ci_upper_bound': interval[1] <= gates['ci_upper_bound'],
               'max_workload_regression': all(row['median_ratio'] <= 1 + gates['max_workload_regression'] for row in rows)}
    return {'median_ratio': ratio, 'relative_gain': 1 - ratio, 'ratio_confidence_interval': interval,
            'confidence': confidence, 'bootstrap_resamples': resamples, 'bootstrap_seed': seed,
            'gates': gates, 'gate_results': results, 'correctness_passed': correctness_passed is True,
            'objective_met': all(results.values()), 'rows': rows}


def compare_protocol_samples(protocol, samples, *, correctness_passed, seed=DEFAULT_BOOTSTRAP_SEED):
    """Codex-compatible comparison (``ai4r-rsi-capsule-performance-comparison:1``)."""
    ids = [ident for split in protocol['splits'] for ident in protocol['splits'][split]['timing_case_ids']]
    need(set(samples) == set(ids) and all(len(samples[i]) == protocol['repetitions'] for i in ids),
         'EXACT_VISIBLE_AND_WITHHELD_TIMING_INVENTORY_REQUIRED')
    minimum = protocol['minimum_relative_gain']
    value = compare_paired_samples(samples, workload_ids=ids, seed=seed, confidence=protocol['confidence'],
        resamples=protocol['bootstrap_resamples'], correctness_passed=correctness_passed,
        gates={'minimum_gain': minimum, 'ci_upper_bound': protocol.get('ci_upper_bound', 1 - minimum),
               'max_workload_regression': protocol['regression_limit']})
    results = value['gate_results']
    return {'schema': COMPARISON_SCHEMA, 'capsule_name': protocol['capsule_name'],
            'median_ratio': value['median_ratio'], 'relative_gain': value['relative_gain'],
            'ratio_confidence_interval': value['ratio_confidence_interval'],
            'correctness_passed': value['correctness_passed'],
            # Codex's claim rule: correctness, CI upper bound and per-workload limit.
            'objective_met': results['correctness'] and results['ci_upper_bound'] and results['max_workload_regression'],
            'rows': value['rows'], 'qualification': protocol['qualification']}
