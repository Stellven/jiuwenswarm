"""Read-only expert-streaming inspection with task-scoped observation publication."""
from __future__ import annotations

import math
from pathlib import Path
import re
import shlex
import struct


def gguf_bytes(path):
    """Read GGUF v2/v3 metadata and tensor directory; never map/read weight data."""
    with Path(path).open('rb') as stream:
        def unpack(fmt):
            size = struct.calcsize('<' + fmt)
            data = stream.read(size)
            if len(data) != size:
                raise ValueError('Truncated GGUF header')
            return struct.unpack('<' + fmt, data)[0]
        def string():
            n = unpack('Q')
            if n > 16 * 1024 * 1024:
                raise ValueError('GGUF string too large')
            data = stream.read(n)
            if len(data) != n:
                raise ValueError('Truncated GGUF string')
            return data.decode('utf-8')
        def skip(kind, depth=0):
            sizes = {0:1, 1:1, 2:2, 3:2, 4:4, 5:4, 6:4, 7:1, 10:8, 11:8, 12:8}
            if kind in sizes:
                stream.seek(sizes[kind], 1)
            elif kind == 8:
                string()
            elif kind == 9 and depth < 8:
                element, count = unpack('I'), unpack('Q')
                if count > 10000000:
                    raise ValueError('GGUF array too large')
                if element in sizes:
                    stream.seek(count * sizes[element], 1)
                else:
                    for _ in range(count):
                        skip(element, depth + 1)
            else:
                raise ValueError('Unknown GGUF metadata type')
        if stream.read(4) != b'GGUF' or unpack('I') not in (2, 3):
            raise ValueError('Expected GGUF v2/v3')
        tensors, metadata = unpack('Q'), unpack('Q')
        if tensors > 1000000 or metadata > 1000000:
            raise ValueError('GGUF directory too large')
        for _ in range(metadata):
            string(); skip(unpack('I'))
        # GGML type -> elements/block, bytes/block (including quantization scales).
        types = {0:(1,4),1:(1,2),2:(32,18),3:(32,20),6:(32,22),7:(32,24),8:(32,34),9:(32,40),
                 10:(256,84),11:(256,110),12:(256,144),13:(256,176),14:(256,210),15:(256,292),
                 16:(256,66),17:(256,74),18:(256,98),19:(256,50),20:(32,18),21:(256,110),
                 22:(256,82),23:(256,136),24:(1,1),25:(1,2),26:(1,4),27:(1,8),28:(1,8),
                 29:(256,56),30:(1,2),34:(256,54)}
        expert, other = 0, 0
        for _ in range(tensors):
            name, dims = string(), unpack('I')
            if not 1 <= dims <= 4:
                raise ValueError('Invalid GGUF tensor dimensions')
            shape = [unpack('Q') for _ in range(dims)]
            kind = unpack('I'); unpack('Q')  # offset, not weight contents
            if kind not in types:
                raise ValueError(f'Unsupported GGML tensor type {kind}')
            block, size = types[kind]
            if shape[0] % block:
                raise ValueError('Invalid GGUF quantized row size')
            count = math.prod(shape) // block * size
            if re.search(r'_exps(?:\.|$)', name):
                expert += count
            else:
                other += count
        return expert, other


def applicability(model_path, argv, meminfo='/proc/meminfo'):
    argv = shlex.split(argv) if isinstance(argv, str) else list(argv)
    result = dict(expert_bytes=None, other_bytes=None, mem_total=None, mem_available=None,
                  experts_cpu_side=None, mmap=None, verdict='unknown', reasons=[])
    reasons = result['reasons']
    try:
        result['expert_bytes'], result['other_bytes'] = gguf_bytes(model_path)
    except (OSError, ValueError, UnicodeError) as exc:
        reasons.append('Model header unavailable: ' + str(exc))
    try:
        mem = {k: int(v) * 1024 for k, v in re.findall(r'^(MemTotal|MemAvailable):\s+(\d+) kB', Path(meminfo).read_text(), re.M)}
        result.update(mem_total=mem.get('MemTotal'), mem_available=mem.get('MemAvailable'))
    except (OSError, ValueError) as exc:
        reasons.append('Memory information unavailable: ' + str(exc))
    cpu = any(a in {'-cmoe', '--cpu-moe'} for a in argv)
    overrides = [argv[i+1] for i, a in enumerate(argv[:-1]) if a in {'-ot', '--override-tensor'}]
    if not cpu and overrides:
        cpu = any(re.search(r'(exps|expert|ffn_).*?=CPU', o, re.I) for o in overrides)
    result['experts_cpu_side'] = True if cpu else None
    mmap = None
    for i, arg in enumerate(argv):
        if arg in {'-lm', '--load-mode'} and i + 1 < len(argv):
            mmap = argv[i+1] == 'mmap'
        if arg in {'--no-mmap', '--no-mmap-load'}:
            mmap = False
        if arg == '--mmap':
            mmap = True
    result['mmap'] = mmap
    if result['expert_bytes'] == 0 or mmap is False:
        result['verdict'] = 'not_applicable'
        reasons.append('Requires MoE expert tensors and mmap loading')
    elif all(result[k] is not None for k in ('expert_bytes','mem_available')) and cpu and mmap:
        if result['expert_bytes'] > result['mem_available'] * 2:
            result['verdict'] = 'applicable'
            reasons.append('CPU-side mapped expert bytes exceed available memory by more than 2x')
        else:
            result['verdict'] = 'not_applicable'
            reasons.append('Expert bytes do not greatly exceed available memory (2x heuristic)')
    else:
        reasons.append('Need expert size, memory headroom, explicit CPU expert placement and mmap evidence')
    return result


def parse_engagement(stderr):
    blocks = {}
    for block, marker in [('config','expert_config: effective'), ('fill','expert_fill: stats'),
                          ('pregate','expert_pregate: stats'), ('readiness','expert_readiness: stats')]:
        rows = []
        for line in stderr.splitlines():
            if marker not in line:
                continue
            row = {}
            for key, value in re.findall(r'(\w+)=([^\s]+)', line.split(marker, 1)[1]):
                try:
                    row[key] = float(value) if '.' in value else int(value)
                except ValueError:
                    row[key] = value
            rows.append(row)
        blocks[block] = dict(status='measured', counters=rows) if rows else dict(status='not_measured')
    def counters(block):
        rows = blocks[block].get('counters', [])
        keys = {k for row in rows for k in row}
        return {k: sum(row[k] for row in rows if isinstance(row.get(k), (int,float))) for k in keys}
    f, p, r = (counters(b) for b in ('fill','pregate','readiness'))
    tokens = r.get('decode_tokens')
    # Fallback only to the printed decode timing token count; never use decode_calls (layers).
    if not tokens:
        matches = re.findall(r'(?<!prompt )\beval time[^\n]*?/\s*(\d+)\s+(?:runs|tokens)', stderr)
        tokens = int(matches[-1]) if matches else None
    def div(n, d):
        return n / d if n is not None and d else None
    derived = dict(decode_tokens=tokens, decode_bytes_read_per_token=div(f.get('decode_bytes_read'),tokens),
                   demand_wait_ms_per_token=div(f.get('decode_fill_wall_ns'),tokens * 1e6 if tokens else None),
                   recall_at_k=div(p.get('hits'),p.get('actual')),
                   readiness_ratio_predicted=div(r.get('decode_ready_bytes_predicted'),
                       r.get('decode_ready_bytes_predicted',0)+r.get('decode_missing_bytes_predicted',0)),
                   readiness_ratio_unpredicted=div(r.get('decode_ready_bytes_unpredicted'),
                       r.get('decode_ready_bytes_unpredicted',0)+r.get('decode_missing_bytes_unpredicted',0)),
                   wasted_bytes_per_token=div(r.get('decode_wasted_async_bytes'),tokens),
                   duplicate_bytes_per_token=div(r.get('decode_duplicate_demand_bytes'),tokens))
    if derived['recall_at_k'] is None and 'recall_at_k' in p:
        derived['recall_at_k'] = p['recall_at_k']
    for state in ('done','inflight','queued','resident'):
        derived['predicted_hits_' + state + '_share'] = div(p.get('hit_'+state),p.get('hits'))
    return dict(**blocks, derived=derived)


def dispatch(store, task_id, capability, inputs):
    from .api import fields
    if capability == 'applicability':
        from .contract import load
        fields(inputs, {'model_path','argv'})
        contract = load(store.get_task(task_id)['contract_id'])
        values = applicability(inputs.get('model_path',contract['model']['path']),
                               inputs.get('argv',contract['workload']['argv']))
        refs = []
    elif capability == 'engagement':
        fields(inputs, {'attempt_id','evaluation_id'})
        if len(inputs) != 1:
            raise ValueError('Supply exactly one of attempt_id or evaluation_id')
        record = store.read(task_id, next(iter(inputs.values())))
        if 'evaluation_id' in inputs:
            refs = record.get('inputs', {}).get('source_artifacts', [])
        else:
            if record.get('kind') != 'lab':
                raise ValueError('engagement requires a lab or A/B attempt')
            refs = record.get('result_refs', [])
        stderr_refs = [ref for ref in refs if ref.endswith(':stderr.txt') or ref.endswith('/stderr.txt')]
        values = dict(runs=[dict(artifact_id=ref, **parse_engagement(store.artifact_bytes(task_id,ref).decode(errors='replace')))
                            for ref in stderr_refs], status='measured' if stderr_refs else 'not_measured')
        refs = stderr_refs
    else:
        raise ValueError('Unknown expert_streaming capability')
    observation = store.append_observation(task_id, dict(kind='expert_streaming_' + capability,
        values=values, source_artifacts=refs, limitations='Read-only inspection; not performance scoring'))
    return dict(**values, evidence=dict(observation_id=observation['obs_id']))
