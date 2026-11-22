"""Static inventory and wall-time accounting for retained quantized traces."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re


TYPES = {'IQ2_XXS', 'IQ4_NL', 'other', 'unknown'}
DEVICES = {'CPU', 'GPU', 'unknown'}
QUANT_OPS = {'quant_matmul', 'dequant', 'fused_quant'}
OPERATIONS = QUANT_OPS | {'activation_quant', 'transfer', 'other', 'unknown'}
EXPERT = re.compile(r'^layers\.\d+\.ffn\.experts\.\d+\.w[123]\.weight$')
STORAGE_LIMITATION = (
    'The source map lists possible kernels and the pack index lists storage roles. '
    'No trace, dispatch selection, runtime kernel time or speed improvement is measured by this inventory.'
)
TRACE_LIMITATION = (
    'Rows report inclusive wall-time unions inside request windows. Different categories can overlap, '
    'and CPU/GPU intersection is reported separately. Fused kernels stay indivisible. '
    'Unknown spans and unobserved wall time retain their own values. Kernel occupancy is not '
    'an exclusive critical-path cost or a model of achievable end-to-end speedup.'
)


def read(artifact):
    with Path(artifact['path']).open('rb') as stream:
        data = stream.read(32 * 1024**2 + 1)
    if len(data) > 32 * 1024**2 or hashlib.sha256(data).hexdigest() != artifact['sha256']:
        raise ValueError('Artifact exceeds the bound or differs from its digest')
    return data


def storage_inventory(text):
    counts = defaultdict(lambda: {'tensors': 0, 'stored_bytes': 0})
    seen = set()
    for line in text.splitlines():
        fields = line.split()
        if not fields or fields[0] != 't':
            continue
        if len(fields) < 6:
            raise ValueError('Incomplete tensor index row')
        name, quant = fields[1:3]
        if name in seen:
            raise ValueError('Duplicate tensor index name')
        seen.add(name)
        if EXPERT.fullmatch(name):
            role = 'routed_expert_matrix'
        elif '.engram.' in name:
            role = 'engram'
        else:
            role = 'other'
        if quant not in {'IQ2_XXS', 'IQ4_NL'} and role != 'routed_expert_matrix':
            continue
        size = int(fields[5])
        if size <= 0:
            raise ValueError('Tensor index size must be positive')
        counts[quant, role]['tensors'] += 1
        counts[quant, role]['stored_bytes'] += size
    if not counts:
        raise ValueError('No quantized storage evidence in the index')
    return [{'quant_type': quant, 'role': role, **value} for (quant, role), value in sorted(counts.items())]


def inventory(pack_index):
    data = read(pack_index)
    source_map = json.loads(Path(__file__).with_name('SOURCES.json').read_text())
    if pack_index['sha256'] != source_map['pack_index_sha256']:
        raise ValueError('Pack index differs from the inventory source-map pin')
    return {
        'schema': 'quant-kernel-static-inventory/1', 'kind': 'analysis',
        'title': 'GB10 quantized kernel source and pack inventory',
        'status': 'source inspected; kernel shares unmeasured',
        'pack_index_sha256': pack_index['sha256'],
        'source_revisions': source_map['source_revisions'],
        'source_rows': source_map['rows'],
        'rows': storage_inventory(data.decode()),
        'wall_shares': None,
        'limitations': STORAGE_LIMITATION,
    }


def bounds(row):
    start, stop = row['start_ns'], row['end_ns']
    if type(start) is not int or type(stop) is not int or not 0 <= start < stop:
        raise ValueError('Expected positive integer nanosecond spans')
    return start, stop


def union_ns(intervals):
    covered = 0
    right = 0
    for start, stop in sorted(intervals):
        covered += max(0, stop - max(start, right))
        right = max(right, stop)
    return covered


def summarize(trace):
    if trace['schema'] != 'quant-kernel-spans/1' or trace['aligned_clock'] is not True:
        raise ValueError('Expected attributed spans and a verified common clock basis')
    for field in ('engine_sha256', 'model_receipt_sha256', 'raw_trace_sha256', 'clock_receipt_sha256'):
        if not re.fullmatch(r'[a-f0-9]{64}', trace[field]):
            raise ValueError(f'Expected pinned trace provenance for {field}')
    if trace['engine'] not in {'llama.cpp', 'Strata'}:
        raise ValueError('Unsupported engine identity')
    spans = []
    for row in trace['spans']:
        device, quant, op = row['device'], row['quant_type'], row['operation']
        if device not in DEVICES or quant not in TYPES or op not in OPERATIONS:
            raise ValueError('Unsupported span label; use unknown for unavailable attribution')
        spans.append((bounds(row), device, quant, op))
    phases = []
    seen = set()
    for phase in trace['windows']:
        label = phase['phase']
        if label not in {'ttft', 'decode'} or label in seen:
            raise ValueError('Provide one measured interval per captured phase')
        seen.add(label)
        start, stop = bounds(phase)
        elapsed = stop - start
        by_category = defaultdict(list)
        target = defaultdict(list)
        unknown = []
        all_spans = []
        for (low, high), device, quant, op in spans:
            a, b = max(start, low), min(stop, high)
            if b <= a:
                continue
            interval = (a, b)
            all_spans.append(interval)
            by_category[device, quant, op].append(interval)
            if 'unknown' in (device, quant, op):
                unknown.append(interval)
            if quant in {'IQ2_XXS', 'IQ4_NL'} and op in QUANT_OPS:
                target[device].append(interval)
        known_union = union_ns(target['CPU'] + target['GPU'])
        cpu_ns, gpu_ns = union_ns(target['CPU']), union_ns(target['GPU'])
        target_ns = union_ns(target['CPU'] + target['GPU'] + target['unknown'])
        phases.append({
            'phase': label, 'elapsed_ns': elapsed,
            'target_quant_observed_union_ns': target_ns,
            'target_quant_observed_fraction': target_ns / elapsed,
            'target_quant_cpu_union_ns': cpu_ns, 'target_quant_gpu_union_ns': gpu_ns,
            'target_quant_cpu_gpu_overlap_ns': cpu_ns + gpu_ns - known_union,
            'unknown_attribution_union_ns': union_ns(unknown),
            'unobserved_ns': elapsed - union_ns(all_spans),
            'rows': [
                {'device': device, 'quant_type': quant, 'operation': op, 'inclusive_ns': observed,
                 'inclusive_fraction': observed / elapsed}
                for (device, quant, op), intervals in sorted(by_category.items())
                for observed in (union_ns(intervals),)
            ],
        })
    if not phases:
        raise ValueError('No measured request phase windows')
    return {
        'schema': 'quant-kernel-wall-profile/1', 'kind': 'analysis',
        'engine': trace['engine'], 'capture_id': trace['capture_id'],
        'provenance': {key: trace[key] for key in ('engine_sha256', 'model_receipt_sha256', 'raw_trace_sha256', 'clock_receipt_sha256')},
        'rows': phases, 'limitations': TRACE_LIMITATION,
    }


def profile(artifact):
    return summarize(json.loads(read(artifact))) | {'normalized_trace_sha256': artifact['sha256']}
