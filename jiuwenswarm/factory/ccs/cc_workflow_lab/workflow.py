"""Bounded stdlib analyses. No host imports, external execution or path inputs."""
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import time
import tracemalloc

LIMIT = 128

def finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(name + ' must be a finite nonnegative number')
    return value

def analyze_receipts(spec):
    rows = spec.get('receipts')
    if not isinstance(rows, list) or not 1 <= len(rows) <= LIMIT:
        raise ValueError('receipts must contain 1..128 rows')
    groups = {}
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('receipt must be an object')
        package, call = row.get('package'), row.get('call')
        if not isinstance(package, str) or not 1 <= len(package) <= 128:
            raise ValueError('package identity required')
        if not isinstance(call, str) or not 1 <= len(call) <= 128 or call in seen:
            raise ValueError('unique call identity required')
        seen.add(call)
        value = finite(row.get('elapsed_s'), 'elapsed_s')
        bucket = groups.setdefault(package, {'elapsed_s': [], 'failures': 0})
        bucket['elapsed_s'].append(value)
        bucket['failures'] += row.get('state') != 'succeeded' or row.get('completeness') != 'complete'
    return {'scope': 'CPU/native factory invocation observations only', 'call_count': len(rows),
            'packages': {name: {'calls': len(g['elapsed_s']), 'failures': g['failures'],
                                 'median_s': statistics.median(g['elapsed_s']),
                                 'total_s': sum(g['elapsed_s'])} for name, g in sorted(groups.items())},
            'total_s': sum(sum(g['elapsed_s']) for g in groups.values()),
            'gpu_improvement_claimed': False, 'admission_granted': False}

def design_workflow(spec):
    count = spec.get('operation_count')
    if type(count) is not int or not 1 <= count <= 32:
        raise ValueError('operation_count must be an integer in 1..32')
    prepare = finite(spec.get('prepare_s', 0), 'prepare_s')
    invoke = finite(spec.get('invoke_s', 0), 'invoke_s')
    analysis = finite(spec.get('analysis_s', 0), 'analysis_s')
    return {'operation_count': count, 'separate': {'prepare_calls': count, 'native_calls': count,
            'estimated_s': count*(prepare+invoke)+analysis},
            'reuse_release': {'prepare_calls': 1, 'native_calls': count,
            'estimated_s': prepare+count*invoke+analysis},
            'cohesive_batch': {'prepare_calls': 1, 'native_calls': 1,
            'estimated_s': prepare+invoke+analysis},
            'assumptions': ['Costs are explicit caller measurements, not a prediction certificate',
                            'Only independent package-local analysis operations may be batched',
                            'Reuse a release only while its sealed implementation and authority remain appropriate'],
            'admission_granted': False}

def fixture():
    return json.loads((Path(__file__).parent/'fixtures/qualification.json').read_text())

def benchmark_fixture(spec):
    repeats = spec.get('repeats', 5)
    if type(repeats) is not int or not 1 <= repeats <= 32:
        raise ValueError('repeats must be an integer in 1..32')
    data = fixture()
    raw = []
    tracemalloc.start()
    try:
        for _ in range(repeats):
            start = time.perf_counter_ns()
            result = analyze_receipts(data)
            raw.append((time.perf_counter_ns()-start)/1e9)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {'fixture_identity_encoding': 'sorted-key Python JSON UTF-8',
            'fixture_sha256': hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),
            'raw_s': raw, 'median_s': statistics.median(raw), 'python_traced_peak_bytes': peak,
            'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'rss_scope': 'Linux process lifetime high water; includes interpreter, not incremental allocation',
            'calls_analyzed_per_repeat': result['call_count'], 'cpu_only': True,
            'gpu_improvement_claimed': False, 'admission_granted': False}

OPERATIONS = {'analyze_receipts': analyze_receipts, 'design_workflow': design_workflow,
              'benchmark_fixture': benchmark_fixture}

def run_batch(spec):
    jobs = spec.get('jobs')
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 16:
        raise ValueError('jobs must contain 1..16 operations')
    # Validate the full envelope before running any operation. No recursive batches.
    for job in jobs:
        if not isinstance(job, dict) or set(job) != {'operation', 'spec'}:
            raise ValueError('each job needs exactly operation and spec')
        if job['operation'] not in OPERATIONS or not isinstance(job['spec'], dict):
            raise ValueError('operation must be in the fixed package-local allowlist')
    return {'results': [{'operation': job['operation'], 'result': OPERATIONS[job['operation']](job['spec'])}
                        for job in jobs], 'cpu_only': True, 'external_execution': False}

DISPATCH = {**OPERATIONS, 'run_batch': run_batch}
