"""Rank routed experts from an LLAMA_MOE_CACHE_TRACE routing trace and write the seeded cache profile.

Trace (llama-moe-cache.cpp at 9048bad8, little endian): "MCT1", u32 n_layer, n_expert_used, n_group; per group
u32 device, n_expert, n_layers, the layers (u32), f64 split, split_sum, u64 group host bytes, device host bytes,
alignment, u32 n_tensors, u64 bytes of one expert per tensor; then one record per slot lookup: i32 layer,
experts per token, n_ids, the ids (i32). A lookup of one token is decode, of more tokens prompt (prefill).

The profile is the strict spark-expert-residency-nominations/1 document the seeded native cache reads (target
muse-spark-open): per layer every expert seen, most hits first, and payload_bytes_before_overhead from the
pack's own expert sizes (gate + up + down nb[2]). It is written private and read-only (mode 0400), as the
reader requires.
"""
import collections
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'weight_pack_compiler' / 'helpers'))
from gguf_pack import load_pack  # noqa: E402

FORMAT = 'spark-expert-residency-nominations/1'
STATUS = 'Ranked candidate pool only. Must truncate by actual byte/slot capacity and reserve dynamic demand slots.'


def read_trace(path):
    data = Path(path).read_bytes()
    if data[:4] != b'MCT1':
        raise ValueError('not an MCT1 routing trace')
    off = 4
    n_layer, n_used, n_group = struct.unpack_from('<III', data, off)
    off += 12
    for _ in range(n_group):
        _dev, _n_expert, nl = struct.unpack_from('<III', data, off)
        off += 12 + 4 * nl + 16 + 24
        nt, = struct.unpack_from('<I', data, off)
        off += 4 + 8 * nt
    counts = {'prompt': collections.defaultdict(collections.Counter), 'decode': collections.defaultdict(collections.Counter)}
    lookups = collections.Counter()
    while off < len(data):
        if off + 12 > len(data):
            raise ValueError('trace ends inside a record')
        il, per, n = struct.unpack_from('<iii', data, off)
        off += 12
        ids = struct.unpack_from(f'<{n}i', data, off)
        off += 4 * n
        phase = 'decode' if per and n // per == 1 else 'prompt'
        counts[phase][il].update(ids)
        lookups[phase] += 1
    return dict(n_layer=n_layer, n_expert_used=n_used, counts=counts, lookups=dict(lookups),
                sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def rank_trace(trace, pack, out=None, prompt_set_sha256=None):
    checks = []

    def add(name, ok, detail):
        checks.append(dict(name=name, status='pass' if ok else 'fail', stage='native CC execution', detail=detail))

    t = read_trace(trace)
    p = load_pack(pack)
    meta = p['metadata']
    arch = meta.get('general.architecture', 'muse-spark')
    n_layer = int(meta.get(f'{arch}.block_count', t['n_layer']))
    n_expert = int(meta.get(f'{arch}.expert_count', 0))
    per_layer = {}
    for row in p['tensors'].values():
        for proj in ('ffn_gate_exps', 'ffn_up_exps', 'ffn_down_exps'):
            if row['name'].endswith(proj + '.weight'):
                layer = int(row['name'].split('.')[1])
                per_layer.setdefault(layer, {})[proj] = row['nbytes'] // int(row['shape'][-1])
    add('trace_matches_pack', t['n_layer'] == n_layer, f"trace {t['n_layer']} layers, pack {n_layer}")
    complete = sorted(per_layer) == list(range(n_layer)) and all(len(v) == 3 for v in per_layer.values())
    add('expert_sizes', complete, f'{len(per_layer)} layers with gate, up and down expert tensors')
    total = collections.defaultdict(collections.Counter)
    for phase in ('prompt', 'decode'):
        for il, c in t['counts'][phase].items():
            total[il].update(c)
    seen = sorted(total)
    add('every_layer_routed', seen == list(range(n_layer)), f'{len(seen)} of {n_layer} layers have lookups')
    bad = [il for il in seen for e in total[il] if not 0 <= e < n_expert]
    add('expert_ids_in_range', not bad, f'ids outside 0..{n_expert - 1} in layers {sorted(set(bad))[:10]}' if bad
        else f'every id in 0..{n_expert - 1}')
    layers, payload = [], 0
    for il in seen:
        ranked = total[il].most_common()
        layers.append(dict(layer=il, expert_ids=[e for e, _ in ranked]))
        payload += len(ranked) * sum(per_layer.get(il, {}).values())
    hits = {phase: [dict(layer=il, hits={str(e): n for e, n in sorted(c.items())}) for il, c in sorted(t['counts'][phase].items())]
            for phase in ('prompt', 'decode')}
    add('both_phases', all(t['lookups'].get(p) for p in ('prompt', 'decode')),
        f"lookups {t['lookups']}")
    doc = None
    if out and all(c['status'] == 'pass' for c in checks if c['name'] != 'both_phases'):
        text = ('{"format":"%s","status":"%s","target":"muse-spark-open","rank_basis":"LLAMA_MOE_CACHE_TRACE hit count on '
                'calibration prompts","source_profile_sha256":"%s","n_layer":%d,"n_expert":%d,'
                '"payload_bytes_before_overhead":%d,"layers":[\n%s\n]}\n') % (
            FORMAT, STATUS, t['sha256'], n_layer, n_expert, payload,
            ',\n'.join('{"layer":%d,"expert_ids":[%s]}' % (l['layer'], ','.join(map(str, l['expert_ids']))) for l in layers))
        json.loads(text)
        out = Path(out)
        if out.exists():
            os.chmod(out, 0o600)
            out.unlink()
        out.write_text(text)
        os.chmod(out, 0o400)
        doc = dict(path=str(out), sha256=hashlib.sha256(text.encode()).hexdigest(), bytes=len(text))
    summary = dict(trace_sha256=t['sha256'], trace_bytes=t['bytes'], lookups=t['lookups'], n_layer=n_layer,
                   n_expert=n_expert, n_expert_used=t['n_expert_used'], pool=sum(len(l['expert_ids']) for l in layers),
                   payload_bytes_before_overhead=payload, prompt_set_sha256=prompt_set_sha256,
                   pack_first_shard=p['files'][0]['path'])
    return dict(done=all(c['status'] == 'pass' for c in checks) and doc is not None, checks=checks,
                profile=doc, summary=summary, hits=hits)
