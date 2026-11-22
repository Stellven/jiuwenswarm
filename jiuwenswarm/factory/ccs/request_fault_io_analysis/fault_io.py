"""Measure snapshot differences around an observed first response token."""
import hashlib
import json
import math
from pathlib import Path


MEMORY_COUNTERS = (
    'pgfault', 'pgmajfault', 'workingset_refault_file', 'workingset_activate_file',
    'pgscan', 'pgsteal', 'pgscan_kswapd', 'pgscan_direct', 'pgsteal_kswapd', 'pgsteal_direct',
)
MEMORY_GAUGES = ('file', 'file_mapped', 'inactive_file', 'active_file')
LIMITATIONS = (
    'Snapshots bracket client-observed response timing and are collected sequentially. '
    'Counters can be batched and include scoped background work. Major faults count demands '
    'rather than physical read bytes; readahead, residency, accounting and reclaim can decouple them. '
    'Process, cgroup and whole-device bytes describe different scopes and are never summed. '
    'Whole-device I/O may include unrelated work. A file-memory gauge change is not bytes read. '
    'These counters do not identify model tensor pages, storage wait on the critical path or a causal TTFT effect.'
)


def uint(value):
    return type(value) is int and value >= 0


def read_pinned(artifact):
    with Path(artifact['path']).open('rb') as stream:
        data = stream.read(8 * 1024**2 + 1)
    if len(data) > 8 * 1024**2 or hashlib.sha256(data).hexdigest() != artifact['sha256']:
        raise ValueError('Request input exceeds limit or differs from its pinned SHA-256')
    return data


def adjusted(start, end):
    if not uint(start) or not uint(end):
        return None, 'unavailable'
    if end < start:
        return None, 'decreased'
    return end - start, 'observed'


def add_metrics(rows, source, resource, start, end, fields, normalization, *, gauge=False, identity_status=None):
    for field in fields:
        a, b = start.get(field), end.get(field)
        if identity_status:
            amount, status = None, identity_status
        elif gauge and uint(a) and uint(b):
            amount, status = b - a, 'observed'
        else:
            amount, status = adjusted(a, b)
        rows.append({
            'source': source,
            'resource': resource,
            'counter': field,
            'unit': 'bytes' if gauge or field in ('read_bytes', 'rbytes') else 'count',
            'kind': 'gauge_change' if gauge else 'counter_delta',
            'start': a if uint(a) else None,
            'end': b if uint(b) else None,
            'delta': amount,
            'per_ttft_second': amount / normalization if normalization and amount is not None and not gauge else None,
            'status': status,
        })


def identity_status(start, end, field, valid):
    if not start or not end:
        return None
    before, after = start.get(field), end.get(field)
    if not valid(before) or not valid(after):
        return 'identity_unverified'
    return 'identity_changed' if before != after else None


def window(start, end, ttft=None):
    if start is None or end is None:
        return {'status': 'boundary_unavailable', 'elapsed_s': None, 'rows': []}
    first, last = start['monotonic_ns'], end['monotonic_ns']
    if (not all(uint(value) for value in (first, last, start['end_monotonic_ns'], end['end_monotonic_ns']))
            or not first <= start['end_monotonic_ns'] <= last <= end['end_monotonic_ns']):
        raise ValueError('Snapshot clocks are missing, overlap or run backwards')

    rows = []
    add_metrics(rows, 'cgroup.memory.stat', 'scope', start['memory_stat'], end['memory_stat'], MEMORY_COUNTERS, ttft)
    add_metrics(rows, 'cgroup.memory.stat', 'scope', start['memory_stat'], end['memory_stat'], MEMORY_GAUGES, ttft, gauge=True)
    start_io, end_io = start['io_stat'], end['io_stat']
    for device in sorted(set(start_io) | set(end_io)):
        add_metrics(rows, 'cgroup.io.stat', device, start_io.get(device, {}), end_io.get(device, {}), ('rbytes', 'rios'), ttft)

    start_process, end_process = start['processes'], end['processes']
    for pid in sorted(set(start_process) | set(end_process)):
        a, b = start_process.get(pid, {}), end_process.get(pid, {})
        name = b.get('comm') or a.get('comm') or 'unknown'
        identity = f'{pid} ({name})'
        status = identity_status(a, b, 'starttime_ticks', uint)
        add_metrics(rows, 'process.stat', identity, a, b, ('minflt', 'majflt'), ttft, identity_status=status)
        add_metrics(rows, 'process.io', identity, a.get('io', {}), b.get('io', {}), ('read_bytes',), ttft,
                    identity_status=status)

    start_disks, end_disks = start['host_disks'], end['host_disks']
    for disk in sorted(set(start_disks) | set(end_disks)):
        a, b = start_disks.get(disk, {}), end_disks.get(disk, {})
        status = identity_status(a, b, 'dev', lambda value: isinstance(value, str) and bool(value))
        add_metrics(rows, 'host.diskstats', disk, a, b, ('read_bytes', 'reads', 'sectors_read'), ttft,
                    identity_status=status)

    return {
        'status': 'observed',
        'elapsed_s': (last - first) / 10**9,
        'start_collection_s': (start['end_monotonic_ns'] - first) / 10**9,
        'end_collection_s': (end['end_monotonic_ns'] - last) / 10**9,
        'source_presence': {
            name: {'start': bool(start[field]), 'end': bool(end[field])}
            for name, field in (
                ('cgroup.memory.stat', 'memory_stat'), ('cgroup.io.stat', 'io_stat'),
                ('processes', 'processes'), ('host.diskstats', 'host_disks'),
            )
        },
        'errors': {'start': start['errors'], 'end': end['errors']},
        'rows': rows,
    }


def analyze(counters, request, hashes):
    if counters['schema'] != 'spark-request-resources/1' or request['resource_windows_sha256'] != hashes['counters']:
        raise ValueError('Request result must identify the same captured resource-windows SHA-256')

    ttft = request.get('ttft_s')
    if ttft is not None and (type(ttft) not in (int, float) or not math.isfinite(ttft) or ttft <= 0):
        raise ValueError('Client TTFT must be a positive finite duration or absent')
    start = counters['snapshots'].get('start')
    first = counters['snapshots'].get('first_token')
    end = counters['snapshots'].get('end')
    if bool(first) != (ttft is not None):
        raise ValueError('First-token snapshot and result disagree on the request boundary')
    windows = {
        'to_first_token': window(start, first, ttft),
        'after_first_token': window(first, end),
        'whole_request': window(start, end),
    }
    return {
        'schema': 'request-fault-io-analysis/1',
        'kind': 'analysis',
        'title': 'Page faults and backing-store reads around first token',
        'sha256': hashes,
        'cgroup': counters.get('cgroup'),
        'request': {
            name: request.get(name)
            for name in ('arm', 'prompt_tokens', 'repeat', 'discard', 'ttft_s', 'wall_s', 'ok')
        },
        'windows': windows,
        'rows': windows['to_first_token']['rows'],
        'limitations': LIMITATIONS,
    }


def analyze_artifacts(artifacts):
    return analyze(json.loads(read_pinned(artifacts['counters'])), json.loads(read_pinned(artifacts['request'])),
                   {name: artifact['sha256'] for name, artifact in artifacts.items()})
