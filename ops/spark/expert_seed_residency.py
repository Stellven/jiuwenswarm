#!/usr/bin/env python3
"""Classify existing expert mincore draws by actual startup admission."""
import argparse
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from source_residency import llama_geometry, merge

EXTENTS = 'spark-gguf-expert-extents/1'
SAMPLE_COLUMNS = ['page_index', 'stratum_pages', 'resident']
PROJECTION = re.compile(r'blk\.(\d+)\.ffn_(gate|up|down)_exps\.weight')
NOMINATION = re.compile(
    r'expert_weight_cache_native_profile: nomination group=\d+ layer=(\d+) rank=\d+ expert=(\d+) admitted=([01])\b')
ACTIVE = re.compile(r'expert_weight_cache_native_profile: active seeds=(\d+) initial_h2d_bytes=(\d+)\b')
KEYS = ('startup_seeded', 'other_expert', 'excluded_boundary')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    raw = path.read_bytes()
    return json.loads(raw), dict(path=str(path), sha256=digest(raw))


def read_layout(manifest):
    if manifest.get('schema') != EXTENTS or len(manifest['files']) != 6:
        raise ValueError('Expected the six-shard expert tensor header index')
    layouts, by_layer, names = {}, defaultdict(list), set()
    for file in manifest['files']:
        entries = []
        for tensor in file['expert_tensors']:
            match = PROJECTION.fullmatch(tensor['name'])
            shape, offset, length = (tensor[k] for k in ('shape', 'offset', 'length'))
            if (not match or tensor['name'] in names or len(shape) not in (3, 4) or shape[2] != 384 or
                    (len(shape) == 4 and shape[3] != 1) or any(dim < 1 for dim in shape) or
                    not 0 <= offset < offset + length <= file['identity']['size'] or length % 384):
                raise ValueError(f"Invalid expert tensor extent {tensor['name']}")
            names.add(tensor['name'])
            layer = int(match[1])
            stride = length // 384
            entries.append((offset, offset + length, layer, stride))
            by_layer[layer].append(stride)
        entries.sort()
        if any(left[1] > right[0] for left, right in zip(entries, entries[1:])):
            raise ValueError('Expert tensor extents overlap')
        if merge((start, end) for start, end, _, _ in entries) != file['regions']['expert']:
            raise ValueError('Expert tensor extents disagree with the original header region union')
        other = sorted(file['regions']['dense'] + file['regions']['engram'])
        for start, end, _, _ in entries:
            if any(lo < end and hi > start for lo, hi in other):
                raise ValueError('Expert tensor payload overlaps a different tensor class')
        resolved = file['resolved_path']
        if resolved in layouts:
            raise ValueError('Repeated indexed model shard')
        layouts[resolved] = dict(identity=file['identity'], entries=entries, offsets=[row[0] for row in entries])
    required = {f'blk.{layer}.ffn_{projection}_exps.weight' for layer in range(40) for projection in ('gate', 'up', 'down')}
    if names != required:
        raise ValueError('Expected separate gate, up and down expert tensors on every layer')
    return layouts, {layer: sum(strides) for layer, strides in by_layer.items()}


def startup_admissions(log, layer_payload):
    nominated, seeded = set(), set()
    marked = log.count('expert_weight_cache_native_profile: nomination ')
    rows = NOMINATION.findall(log)
    active = ACTIVE.findall(log)
    if not marked or len(rows) != marked or len(active) != 1:
        raise ValueError('Startup log needs complete nomination rows and one active profile')
    for layer_text, expert_text, admitted in rows:
        layer, expert = int(layer_text), int(expert_text)
        key = layer, expert
        if layer not in layer_payload or not 0 <= expert < 384 or key in nominated:
            raise ValueError('Repeated or invalid startup expert nomination')
        nominated.add(key)
        if admitted == '1':
            seeded.add(key)
    count, uploaded = map(int, active[0])
    payload = sum(layer_payload[layer] for layer, _ in seeded)
    if not seeded or count != len(seeded) or uploaded != payload:
        raise ValueError('Actual startup seeds or uploaded bytes disagree with exact projection extents')
    return seeded, uploaded


def sample_class(source, byte_start, byte_end, seeded):
    index = bisect_right(source['offsets'], byte_start) - 1
    if index < 0:
        return 'excluded_boundary'
    start, end, layer, stride = source['entries'][index]
    if byte_end > end:
        return 'excluded_boundary'
    expert = (byte_start - start) // stride
    if (byte_end - 1 - start) // stride != expert:
        return 'excluded_boundary'
    return 'startup_seeded' if (layer, expert) in seeded else 'other_expert'


def classify(snapshot, layouts, seeded):
    if snapshot.get('schema') != 'spark-source-residency/1':
        raise ValueError('Expected the retained source residency snapshot schema')
    page, step = (snapshot[key] for key in ('page_size', 'pages_per_sample'))
    if type(page) is not int or type(step) is not int or page <= 0 or step <= 0:
        raise ValueError('Invalid page sampling geometry')
    draws = snapshot['views']['llama']['files']
    if len(draws) != len(layouts) or {f['resolved_path'] for f in draws} != set(layouts):
        raise ValueError('Snapshot and index model shard sets differ')
    totals = {key: dict(sampled_pages=0, resident_sampled_pages=0, stratum_weight_pages=0,
                        resident_stratum_weight_pages=0) for key in KEYS}
    fingerprints = {}
    for file in draws:
        path = file['resolved_path']
        source = layouts[path]
        if file['identity'] != source['identity'] or file['expert_sample_columns'] != SAMPLE_COLUMNS:
            raise ValueError('Sample inode, size, mtime or expert detail columns differ from the header index')
        last, weights, resident_samples, resident_weights = -1, 0, 0, 0
        fingerprint = []
        for page_index, weight, resident in file['expert_page_samples']:
            if (type(page_index) is not int or type(weight) is not int or type(resident) is not int or
                    not last < page_index or page_index * page >= file['identity']['size'] or
                    not 1 <= weight <= step or resident not in (0, 1)):
                raise ValueError('Expert draw order, file range, weight or residency bit is invalid')
            last = page_index
            fingerprint.append((page_index, weight))
            byte_start = page_index * page
            result = totals[sample_class(source, byte_start, byte_start + page, seeded)]
            result['sampled_pages'] += 1
            result['resident_sampled_pages'] += resident
            result['stratum_weight_pages'] += weight
            result['resident_stratum_weight_pages'] += weight * resident
            weights += weight
            resident_samples += resident
            resident_weights += weight * resident
        measured = file['regions']['expert']
        if (len(fingerprint), weights, resident_samples, resident_weights) != tuple(measured[k] for k in (
                'sampled_pages', 'intersecting_pages', 'resident_sampled_pages', 'estimated_resident_pages')):
            raise ValueError('Expert draw detail disagrees with the original aggregate sample counters')
        fingerprints[path] = fingerprint
    for key in ('startup_seeded', 'other_expert'):
        result = totals[key]
        weight = result['stratum_weight_pages']
        result['weighted_resident_fraction'] = result['resident_stratum_weight_pages'] / weight if weight else None
    return totals, (page, step, snapshot['seed'], fingerprints)


def utc(stamp):
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        raise ValueError('Naive receipt timestamp')
    return parsed


def analyze(extents, scope, snapshot_arguments):
    manifest, index_ref = read_json(extents)
    layouts, layer_payload = read_layout(manifest)
    scope = scope.resolve()
    kernel, kernel_ref = read_json(scope / 'scope.json')
    load, load_ref = read_json(scope / 'load-ready.json')
    stopped, stop_ref = read_json(scope / 'result.json')
    if stopped['returncode'] or stopped['reason'] or stopped['scope_verified'] is not True:
        raise ValueError('Expected an orderly, completed capped scope')
    log_path = scope / 'stderr.log'
    raw = log_path.read_bytes()
    seeded, bytes_copied = startup_admissions(raw.decode(errors='replace'), layer_payload)
    samples, previous, prior_fingerprint = [], utc(load['ready_at']), None
    seen = set()
    for entry in snapshot_arguments:
        label, separator, relative = entry.partition('=')
        if not separator or not relative or (not samples and label != 'load-ready') or label in seen:
            raise ValueError('Supply load-ready=SNAPSHOT first, then distinct request LABEL=SNAPSHOT arguments')
        path = (scope / relative).resolve()
        if not path.is_relative_to(scope):
            raise ValueError('Snapshot path escapes the captured scope')
        snapshot, receipt = read_json(path)
        start, end = (utc(snapshot[k]) for k in ('started', 'completed'))
        if not previous <= start <= end <= utc(stopped['stop']) or snapshot['scope_accounting']['path'] != kernel['cgroup']:
            raise ValueError('Snapshot order, server readiness or cgroup identity differs from its scope')
        if label != 'load-ready':
            if not re.fullmatch(r'(?:rep|warmup)-\d+-(?:512|2048)', label):
                raise ValueError('Request label must identify a retained 512- or 2048-token request')
            result, request_ref = read_json(scope / label / 'result.json')
            if not end <= utc(result['started']):
                raise ValueError('Snapshot was taken after the named request started')
            receipt['request_receipt'] = request_ref
        totals, fingerprint = classify(snapshot, layouts, seeded)
        if prior_fingerprint is not None and fingerprint != prior_fingerprint:
            raise ValueError('Repeated snapshots did not sample the same page and stratum identities')
        samples.append(dict(label=label, completed=snapshot['completed'], receipt=receipt, totals=totals))
        previous, prior_fingerprint = end, fingerprint
        seen.add(label)
    return dict(schema='spark-seeded-expert-residency/1', scope=str(scope), index=index_ref, scope_receipt=kernel_ref,
                readiness=load_ref, closure=stop_ref, startup_log=dict(path=str(log_path), sha256=digest(raw)),
                startup_initial_h2d_bytes=bytes_copied, admitted_layer_expert_ids=sorted(seeded), snapshots=samples,
                limitations=[
                    'Each weighted fraction is the resident share of the original deterministic sampling weights observed in that group. Strata can span multiple classes, so group weights estimate group size.',
                    'Pages that intersect multiple slices or a tensor edge are excluded from both expert classes.',
                    'The startup-seeded class uses actual positive admissions at initialization. Later demand replacements can change GPU-bank membership. The measurements describe CPU file-page residency.',
                ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    index = modes.add_parser('index', help='Read the six GGUF headers only')
    index.add_argument('--model', required=True, type=Path)
    index.add_argument('--converter', required=True, type=Path)
    summary = modes.add_parser('analyze', help='Use retained receipts without touching model files')
    summary.add_argument('--extents', required=True, type=Path)
    summary.add_argument('--scope', required=True, type=Path)
    summary.add_argument('--snapshot', action='append', required=True, metavar='LABEL=PATH_UNDER_SCOPE')
    for mode in (index, summary):
        mode.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.mode == 'index':
        result = dict(schema=EXTENTS, **llama_geometry(args.model, args.converter, expert_extents=True))
        read_layout(result)
    else:
        result = analyze(args.extents, args.scope, args.snapshot)
    with args.out.open('x') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')


if __name__ == '__main__':
    main()
