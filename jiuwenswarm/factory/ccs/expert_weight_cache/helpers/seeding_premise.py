"""CPU-only paired replay for the pinned AQBC cache's unseeded and seeded modes."""

from collections import Counter, OrderedDict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import struct


STAGE = 'native CC execution'
TRACE_MANIFEST = 'factory.muse-seeding-profile/1'
SEED_PROFILE = 'factory.muse-expert-seed-profile/1'
PREMISE = 'factory.muse-seeding-premise/1'
CELLS = {'first-request', 'warm-512', 'warm-2048', 'follow-up'}
SHA256 = re.compile(r'[0-9a-f]{64}')
MAX_BYTES = 64 * 1024 * 1024


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical_digest(document):
    return digest(json.dumps(document, sort_keys=True, separators=(',', ':')).encode())


def read_bound(ref):
    path = Path(ref['path'])
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES and digest(data) == ref['sha256'], f'Evidence size or digest mismatch: {path}')
    return data


@dataclass(frozen=True)
class Group:
    layers: tuple
    experts: int
    tensor_bytes: tuple
    slots: int


@dataclass(frozen=True)
class Lookup:
    start: int
    end: int
    layer: int
    projection: int
    tokens: int
    experts: tuple


def read_trace(data, cache_mib):
    require(data[:4] == b'MCT2', 'Need an MCT2 trace with both cache paths. MCT1 omits read-only prefill.')
    offset = 4

    def consume(fmt):
        nonlocal offset
        fields = struct.Struct('<' + fmt)
        require(offset + fields.size <= len(data), f'Truncated trace at byte {offset}')
        values = fields.unpack_from(data, offset)
        offset += fields.size
        return values

    layers, n_used, n_groups = consume('3I')
    require(0 < layers <= 1024 and 0 < n_used <= 64 and 0 < n_groups <= layers, 'Invalid cache header')
    groups, by_layer = [], {}
    for _ in range(n_groups):
        _device, experts, layer_count = consume('3I')
        require(n_used <= experts <= 65536 and 0 < layer_count <= layers, 'Invalid group dimensions')
        group_layers = consume(f'{layer_count}I')
        require(len(set(group_layers)) == layer_count and all(il < layers and il not in by_layer for il in group_layers),
                'Duplicate or invalid cached layer')
        split, split_sum = consume('2d')
        host_bytes, device_bytes, alignment = consume('3Q')
        n_tensors, = consume('I')
        require(math.isfinite(split_sum) and 0 < split <= split_sum and 0 < host_bytes <= device_bytes
                and 0 < alignment <= 65536 and 0 < n_tensors <= 4, 'Invalid cache allocation inputs')
        tensor_bytes = consume(f'{n_tensors}Q')
        require(all(tensor_bytes) and host_bytes == experts * layer_count * sum(tensor_bytes), 'Group byte count mismatch')
        budget = int(float(cache_mib * 2**20) * split / split_sum * host_bytes / device_bytes)

        # Cached slots plus the extra MMQ padding slot, with CPU share pinned to zero.
        low, high = 0, layer_count * experts
        while low < high:
            mid = (low + high + 1) // 2
            allocation = sum(((size * (mid + 1) + alignment - 1) // alignment) * alignment for size in tensor_bytes)
            if allocation <= budget:
                low = mid
            else:
                high = mid - 1
        group = Group(group_layers, experts, tensor_bytes, low if low >= n_used else 0)
        groups.append(group)
        by_layer.update({il: group for il in group_layers})

    header_end = offset
    lookups = []
    while offset < len(data):
        start = offset
        layer, per_token, count, projection = consume('4i')
        group = by_layer.get(layer)
        require(group and group.slots and 0 < per_token <= n_used and
                -1 <= projection < len(group.tensor_bytes) and 0 < count <= 65536,
                f'Invalid lookup at byte {start}')
        if projection == -1:
            experts = consume(f'{count}i')
            routes = count
            require(routes <= 32 * per_token and len(set(experts)) <= group.slots, 'Invalid demand-cache lookup size')
        else:
            require(count <= group.experts, 'Invalid read-only expert count')
            pairs = consume(f'{2 * count}i')
            experts, frequencies = pairs[::2], pairs[1::2]
            routes = sum(frequencies)
            require(len(set(experts)) == count and all(0 < num <= routes // per_token for num in frequencies),
                    'Invalid read-only route counts')
        require(routes % per_token == 0 and all(0 <= expert < group.experts for expert in experts),
                f'Invalid expert IDs or incomplete routes at byte {start}')
        lookups.append(Lookup(start, offset, layer, projection, routes // per_token, experts))
    require(lookups, 'The trace contains no cache lookups')
    return header_end, groups, by_layer, lookups


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


class Cache:
    """The pinned engine's eight CRF classes, layer clock and demand replacement."""

    def __init__(self, group, seeds):
        self.slots = group.slots
        self.classes = [OrderedDict() for _ in range(8)]
        self.resident = {}
        self.clock = Counter()
        self.last_used = {}
        self.crf = {}
        for key in seeds:
            self.resident[key] = 0
            self.classes[0][key] = None
            self.last_used[key] = 0

    def touch(self, key, category):
        previous = self.resident.get(key)
        if previous is not None:
            self.classes[previous].pop(key)
        self.classes[category][key] = None
        self.resident[key] = category

    def victim(self, protected):
        victim, best = None, -1.0
        for category, members in enumerate(self.classes):
            candidate = next((key for key in members if key not in protected), None)
            if candidate is None:
                continue
            score = math.ldexp(self.clock[candidate[0]] - self.last_used[candidate], -category)
            if score > best:
                victim, best = candidate, score
        require(victim is not None, 'No unselected cache slot to replace')
        self.classes[self.resident.pop(victim)].pop(victim)

    def lookup(self, row):
        keys = [(row.layer, expert) for expert in dict.fromkeys(row.experts)]
        hits = sum(key in self.resident for key in keys)
        if row.projection >= 0:
            return hits, len(keys) - hits  # Bulk transfers neither fill nor age the cache.

        now = self.clock[row.layer]
        missing = []
        for key in keys:
            age = now - self.last_used.get(key, now)
            decayed = f32(self.crf.get(key, 0.0) * f32(2.0 ** f32(-age / 128)))
            self.crf[key] = f32(decayed + 1.0)
            self.last_used[key] = now
            if key in self.resident:
                self.touch(key, min(7, int(f32(math.log2(self.crf[key])))))
            else:
                missing.append(key)
        protected = set(keys)
        for key in sorted(missing):
            if len(self.resident) == self.slots:
                self.victim(protected)
            self.touch(key, min(7, int(f32(math.log2(self.crf[key])))))
        self.clock[row.layer] += row.tokens
        return hits, len(missing)


def split_requests(manifest, trace_sha, parent_sha, start, lookups):
    require(manifest['format'] == TRACE_MANIFEST and manifest['trace_sha256'] == trace_sha
            and manifest['parent_sha256'] == parent_sha
            and SHA256.fullmatch(manifest['profiling_library_sha256']), 'Manifest does not bind the trace and parent')
    by_offset = {row.start: index for index, row in enumerate(lookups)}
    by_offset[lookups[-1].end] = len(lookups)
    requests = manifest['requests']
    require(isinstance(requests, list) and requests, 'No request ledger')
    ids, calibration, lab_prompts, cells, indexed = set(), set(), set(), set(), []
    for item in requests:
        name, cell, cohort = item['id'], item['cell'], item['cohort']
        end = item['trace_end']
        require(isinstance(name, str) and name and name not in ids, 'Missing or duplicate request ID')
        require(item['trace_start'] == start and type(end) is int and end in by_offset and end >= start,
                f'{name}: trace offsets must partition complete native records')
        ids.add(name)
        rows = lookups[by_offset[start]:by_offset[end]]
        if cell != 'startup':
            prompt = item['prompt_sha256']
            require(SHA256.fullmatch(prompt) and type(item['prompt_n']) is int and item['prompt_n'] >= 0
                    and type(item['generated_n']) is int and item['generated_n'] > 0,
                    f'{name}: missing prompt/realized-token evidence')
            if cohort == 'heldout':
                require(not calibration and cell in CELLS and item['cache_prompt'] is True and rows,
                        f'{name}: held-out replay is missing traffic or does not match the AQBC request settings')
                require(cells or (cell == 'first-request' and not lab_prompts),
                        f'{name}: the first-request observation must precede other lab requests')
                lab_prompts.add(prompt)
                cells.add(cell)
            elif cohort == 'calibration':
                require(item['cache_prompt'] is False and rows, f'{name}: calibration must cover independently routed prompts')
                calibration.add(prompt)
            else:
                require(cohort == 'warmup' and not calibration, f'{name}: invalid request ordering or cohort')
                lab_prompts.add(prompt)
        else:
            require(cohort == 'warmup' and not indexed, 'Startup traffic must precede requests')
        indexed.append((item, rows))
        start = end
    require(start == lookups[-1].end and cells == CELLS and calibration and not calibration & lab_prompts,
            'Need complete cache traffic for all four held-out cells and distinct calibration prompts')
    return indexed


def rank_profile(groups, by_layer, requests, manifest_sha, parent_sha, trace_sha):
    traffic = Counter()
    for request, rows in requests:
        if request['cohort'] == 'calibration':
            for row in rows:
                sizes = by_layer[row.layer].tensor_bytes
                weight = sum(sizes) if row.projection == -1 else sizes[row.projection]
                for expert in set(row.experts):
                    traffic[row.layer, expert] += weight

    result, seeds, upload_bytes = [], {}, 0
    for index, group in enumerate(groups):
        dynamic_reserve = (group.slots + 7) // 8
        ranked = sorted((key for key in traffic if key[0] in group.layers), key=lambda key: (-traffic[key], key))
        selected = ranked[:group.slots - dynamic_reserve]
        seeds[group] = selected
        result.append({'group': index, 'slots': group.slots, 'dynamic_reserve_slots': dynamic_reserve,
                       'entries': [{'layer': il, 'expert_id': expert} for il, expert in selected]})
        upload_bytes += len(selected) * sum(group.tensor_bytes)
    profile = {'format': SEED_PROFILE, 'parent_sha256': parent_sha, 'trace_sha256': trace_sha,
               'manifest_sha256': manifest_sha, 'startup_upload_bytes': upload_bytes, 'groups': result}
    return profile, seeds


def simulate(groups, by_layer, requests, seeds):
    caches = {group: Cache(group, seeds.get(group, ())) for group in groups if group.slots}
    totals = {}
    for request, rows in requests:
        if request['cohort'] == 'calibration':
            break
        stats = Counter(demand_hits=0, demand_misses=0, read_only_hits=0, read_only_misses=0,
                        hit_bytes=0, host_bytes=0)
        for row in rows:
            group = by_layer[row.layer]
            hits, misses = caches[group].lookup(row)
            if row.projection < 0:
                stats['demand_hits'] += hits
                stats['demand_misses'] += misses
                bytes_per_expert = sum(group.tensor_bytes)
            else:
                stats['read_only_hits'] += hits
                stats['read_only_misses'] += misses
                bytes_per_expert = group.tensor_bytes[row.projection]
            stats['hit_bytes'] += hits * bytes_per_expert
            stats['host_bytes'] += misses * bytes_per_expert
        if request['cohort'] == 'heldout':
            output = totals.setdefault(request['cell'], Counter())
            output.update(stats)
    return {
        cell: dict(values, byte_hit_rate=values['hit_bytes'] / (values['hit_bytes'] + values['host_bytes']))
        for cell, values in totals.items()
    }


def check_premise(request):
    try:
        parent_ref = request['parent']
        manifest_ref = request['manifest']
        trace_ref = request['trace']
        parent = json.loads(read_bound(parent_ref))
        manifest = json.loads(read_bound(manifest_ref))
        launch = parent['launch_config']
        args = launch['args']
        require(parent['parent'] == 'AQBC' and parent['engine_source']['commit'] and launch['request']['cache_prompt'] is True
                and args[args.index('--moe-cache-cpu-share') + 1] == '0',
                'Premise requires the pinned AQBC zero-CPU cache and prompt-reuse configuration')
        cache_mib = int(args[args.index('--moe-cache-mib') + 1])
        require(0 < cache_mib <= 110000, 'Cache capacity outside the pinned device budget')
        data = read_bound(trace_ref)
        start, groups, by_layer, lookups = read_trace(data, cache_mib)
        requests = split_requests(manifest, trace_ref['sha256'], parent_ref['sha256'], start, lookups)
        heldout = [row for item, rows in requests if item['cohort'] == 'heldout' for row in rows]
        require(any(row.projection == -1 for row in heldout) and any(row.projection >= 0 for row in heldout),
                'No paired measurement of both slot-map and read-only traffic')
        profile, seeds = rank_profile(groups, by_layer, requests, manifest_ref['sha256'],
                                      parent_ref['sha256'], trace_ref['sha256'])
        baseline = simulate(groups, by_layer, requests, {})
        seeded = simulate(groups, by_layer, requests, seeds)
        avoided = {cell: baseline[cell]['host_bytes'] - seeded[cell]['host_bytes'] for cell in sorted(CELLS)}
        may_build = sum(avoided.values()) > 0 and avoided['first-request'] >= 0
        reason = ('Seeded replay avoids host expert uploads on held-out traffic' if may_build else
                  'No net host-upload headroom without regressing the first request')
        result = dict(format=PREMISE, may_build=may_build, reason=reason,
                      parent_sha256=parent_ref['sha256'], trace_sha256=trace_ref['sha256'], manifest_sha256=manifest_ref['sha256'],
                      profile=profile, profile_sha256=canonical_digest(profile), baseline=baseline, seeded=seeded,
                      avoided_host_bytes=avoided, metric_scope='Cache payload bytes before MMQ tail padding; not measured latency')
        return dict(done=True, checks=[dict(name='heldout_cache_replay', status='pass', stage=STAGE, detail=reason)], premise=result)
    except (AttributeError, IndexError, KeyError, OSError, OverflowError, TypeError, ValueError) as error:
        reason = str(error)
        return dict(done=False, checks=[dict(name='heldout_cache_replay', status='fail', stage=STAGE, detail=reason)],
                    premise=dict(format=PREMISE, may_build=False, reason=reason))
