"""Analyze historical route counts and indexed expert payloads."""
import hashlib
import json
from pathlib import Path
import re
import struct


EXPERT_TENSOR = re.compile(r'layers\.(\d+)\.ffn\.experts\.(\d+)\.w([123])\.weight')
PROFILE_EXTRA_ROWS = 8
LIMITATION = (
    'Historical Strata counters pool prefill and decode. Indexed payload bytes '
    'exclude allocation, padding, workspaces and transfers. Coverage is a static '
    'selection metric and provides no cache-hit, latency or bandwidth measurement.'
)


def read_pinned(path, expected, max_bytes):
    with Path(path).open('rb') as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Input exceeds size limit or differs from its pinned SHA-256')
    return data


def profile_rows(data, layers, experts):
    row_bytes = experts * 4
    if len(data) % row_bytes or not layers <= len(data) // row_bytes <= layers + PROFILE_EXTRA_ROWS:
        raise ValueError('Profile shape differs from the supplied model dimensions')
    rows = struct.iter_unpack(f'<{experts}I', data)
    return list(rows)[:layers]


def indexed_expert_roles(index, layers, experts):
    weights = {}
    for line in index.splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[0] != 't':
            continue
        match = EXPERT_TENSOR.fullmatch(fields[1])
        if match is None:
            continue
        layer, expert, role = map(int, match.groups())
        key = layer, expert, role
        if len(fields) < 6 or layer >= layers or expert >= experts or key in weights:
            raise ValueError('Out-of-range, missing or duplicate indexed expert tensor')
        size = int(fields[5])
        if size <= 0:
            raise ValueError('Indexed expert tensor bytes must be positive')
        weights[key] = size
    if len(weights) != layers * experts * 3:
        raise ValueError('Index must name w1, w2 and w3 for every main-layer expert')
    return weights


def expert_bytes(index, layers, experts):
    weights = indexed_expert_roles(index, layers, experts)
    return [
        [sum(weights[layer, expert, role] for role in (1, 2, 3)) for expert in range(experts)]
        for layer in range(layers)
    ]


def analyze(request):
    layers = request['layers']
    experts = request['experts_per_layer']
    ks = sorted(set(request['top_k']))
    if not 1 <= layers <= 256 or not 1 <= experts <= 4096 or not ks or not 1 <= min(ks) <= max(ks) <= experts:
        raise ValueError('Invalid model dimensions or tier sizes')
    hashes = request['sha256']
    profile_limit = (layers + PROFILE_EXTRA_ROWS) * experts * 4
    before = profile_rows(read_pinned(request['before'], hashes['before'], profile_limit), layers, experts)
    after = profile_rows(read_pinned(request['after'], hashes['after'], profile_limit), layers, experts)
    weights = expert_bytes(
        read_pinned(request['tensor_index'], hashes['tensor_index'], 64 * 1024**2).decode(),
        layers, experts,
    )
    deltas = [
        [end - start for start, end in zip(prior, later, strict=True)]
        for prior, later in zip(before, after, strict=True)
    ]
    if any(delta < 0 for row in deltas for delta in row):
        raise ValueError('Counter decreased in a main layer')
    total = sum(map(sum, deltas))
    if total == 0:
        raise ValueError('No observed main-layer routes')
    rankings = [sorted(range(experts), key=lambda expert: (-row[expert], expert)) for row in before]
    tiers = []
    for k in ks:
        chosen = [ranking[:k] for ranking in rankings]
        covered = sum(deltas[layer][expert] for layer, selected in enumerate(chosen) for expert in selected)
        payload = sum(weights[layer][expert] for layer, selected in enumerate(chosen) for expert in selected)
        tiers.append({
            'k_per_layer': k,
            'fraction_slots': k / experts,
            'counter_delta_in_selected': covered,
            'fraction_new_routes': covered / total,
            'indexed_payload_bytes': payload,
            'indexed_payload_gib': payload / 1024**3,
        })
    return {
        'schema': 'routing-profile-analysis/1',
        'kind': 'analysis',
        'title': 'Historical Strata expert routing coverage',
        'layers': layers,
        'experts_per_layer': experts,
        'sha256': hashes,
        'count_delta': total,
        'indexed_payload_bytes_all_experts': sum(map(sum, weights)),
        'rows': tiers,
        'top_expert_ids_by_layer': [ranking[:max(ks)] for ranking in rankings],
        'limitations': LIMITATION,
    }


def verify(request, report):
    expected = analyze(request)
    return json.dumps(report, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True)
