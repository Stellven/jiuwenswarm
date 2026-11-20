#!/usr/bin/env python3
"""Audit the retained five-gate readbacks from the combined Spark scope."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re


ARM = 'D'
SOURCE = '59493673e75a9b4153733a862fd09951d3705616'
EXPERT = re.compile(r'blk\.(\d+)\.ffn_(gate|up|down)_exps\.weight')
ASSIGNMENT = re.compile(r'weight_placement_planner: assignment name="([^"]+)" planned=(\w+) actual=(\w+) bytes=(\d+)')
BANK = re.compile(r'CUDA0 MoE cache size = ([\d.]+) MiB for ([\d.]+) MiB of host experts, ([\d.]+)% of the misses on the CPU')
LOSSES = ('capacity_lost', 'route_lost', 'contended_lost', 'writer_lost')


def marker(log, name):
    lines = re.findall(re.escape(name) + r': ([^\n]+)', log)
    stats = [{k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', line)} for line in lines if line.startswith('stats ')]
    return dict(active=[line for line in lines if line.startswith('active ')],
                declined=[line[10:-1] for line in lines if line.startswith('inactive (') and line.endswith(')')],
                stats=stats)


def trace_evidence(path, recorder):
    if not path.is_file():
        return dict(status='absent', summary=None)
    digest = hashlib.sha256()
    phase = defaultdict(Counter)
    layers = defaultdict(set)
    requests = set()
    sums = Counter()
    summary = None
    with path.open('rb') as source:
        for line in source:
            digest.update(line)
            try:
                entry = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                sums['malformed_rows'] += 1
                continue
            if not isinstance(entry, dict):
                sums['malformed_rows'] += 1
                continue
            if summary is not None:
                sums['after_summary'] += 1
                continue
            if entry.get('type') == 'summary':
                summary = entry
                continue
            if entry.get('type') != 'event':
                sums['unknown_record_types'] += 1
                continue
            if not {'phase', 'expert_ids', 'microbatch', 'layer', 'request_id', 'bytes_transferred'} <= entry.keys():
                sums['malformed_rows'] += 1
                continue
            sums['event_rows'] += 1
            by_phase = phase[entry['phase']]
            by_phase['event_rows'] += 1
            by_phase['route_rows'] += len(entry['expert_ids'])
            by_phase['expert_selections'] += sum(map(len, entry['expert_ids']))
            batch, layer = entry['microbatch'], entry['layer']
            sums['duplicate_microbatch_layer'] += int(layer in layers[batch])
            layers[batch].add(layer)
            if entry['request_id'] is not None:
                requests.add(entry['request_id'])
            requests.update(row['request_id'] for row in entry.get('rows', ()) if row['request_id'] is not None)
            if entry['bytes_transferred'] is None:
                sums['null_transfer_rows'] += 1
                by_phase['null_transfer_rows'] += 1
            else:
                sums['submitted_bytes'] += entry['bytes_transferred']
                by_phase['submitted_bytes'] += entry['bytes_transferred']
    problem = any(sums[key] for key in ('malformed_rows', 'after_summary', 'unknown_record_types', 'duplicate_microbatch_layer'))
    consistent = bool(summary and not problem and summary['written'] == sums['event_rows'] and
                      summary['expected'] == summary['written'] + summary['lost'] and
                      summary['lost'] == sum(summary[key] for key in LOSSES) and
                      (summary['writer_lost'] or summary['transfer_incomplete'] == sums['null_transfer_rows']) and
                      summary['bytes_transferred'] == sums['submitted_bytes'] and recorder['stats'] == [
                          dict(events=summary['written'], lost=summary['lost'], bytes=summary['bytes_transferred'])])
    incomplete_layers = [dict(microbatch=batch, missing=sorted(set(range(40)) - observed),
                              unexpected=sorted(observed - set(range(40))))
                         for batch, observed in layers.items() if observed != set(range(40))]
    status = ('missing-terminal-summary' if summary is None else 'inconsistent' if not consistent else
              'observed-loss' if summary['lost'] or incomplete_layers else 'route-complete-as-recorded')
    return dict(status=status, sha256=digest.hexdigest(), summary=summary, consistent=consistent,
                transfer_scope='Recorded submitted expert copies. Startup, elapsed DMA time, and saved bytes are outside this count.', **sums,
                request_ids=sorted(requests), microbatches=len(layers), incomplete_route_layers=incomplete_layers,
                phase_counts=phase)


def readback(scope):
    raw = (scope / 'stderr.log').read_bytes()
    log = raw.decode(errors='replace')
    cap = json.loads((scope / 'result.json').read_bytes())
    load = json.loads((scope / 'load-ready.json').read_bytes())
    if (cap['arm'] != ARM or load['source_commit'] != SOURCE or cap['returncode'] or cap['reason'] or
            not cap['scope_verified'] or any(int(cap['memory_events'].get(k, 0)) for k in ('oom', 'oom_kill', 'oom_group_kill'))):
        raise ValueError('Combined gate evidence requires the expected clean, capped source')
    rows = ASSIGNMENT.findall(log)
    expert = [(name, plan, actual, int(size)) for name, plan, actual, size in rows if EXPERT.fullmatch(name)]
    expected = {f'blk.{n}.ffn_{projection}_exps.weight' for n in range(40) for projection in ('gate', 'up', 'down')}
    planned_rows = [dict(name=name, planned=plan, actual=actual, bytes=size) for name, plan, actual, size in expert if plan != 'stock']
    marker_classes = {label: dict(assigned=int(assigned), stock=int(stock)) for label, assigned, stock in
                      re.findall(r'weight_placement_planner: assignment class=(\w+) assigned=(\d+) stock=(\d+)', log)}
    equivalent = (len(expert) == 120 and {row[0] for row in expert} == expected and
                  {row[2] for row in expert} == {'CPU_Mapped'} and len(planned_rows) == 1 and
                  planned_rows[0]['name'] == 'blk.0.ffn_gate_exps.weight' and planned_rows[0]['planned'] == 'CPU' and
                  marker_classes.get('expert') == dict(assigned=1, stock=119))
    placement = dict(marker(log, 'weight_placement_planner'), all_assignment_rows=len(rows), expert_assignment_rows=len(expert),
                     expert_buffers=dict(Counter(row[2] for row in expert)), expert_payload_bytes=sum(row[3] for row in expert),
                     planned_experts=planned_rows, classes=marker_classes, cpu_equivalent=equivalent)
    recorder = marker(log, 'runtime_event_recorder')
    recorder['trace'] = trace_evidence(scope / 'events.jsonl', recorder)
    mapper = marker(log, 'batch_layout_mapper')
    mapper['observed_cuts'] = [dict(length=int(length), cached_prefix=int(cached), begin=int(begin), end=int(end), max_rows=int(limit))
        for length, cached, begin, end, limit in re.findall(
            r'batch_layout_mapper: layout length=(\d+) cached_prefix=(\d+) begin=(\d+) end=(\d+) max_rows=(\d+)', log)]
    banks = [dict(allocated_mib=float(allocation), host_experts_mib=float(host), cpu_miss_share_pct=float(share))
             for allocation, host, share in BANK.findall(log)]
    return dict(schema='spark-combined-gates/1', arm=ARM, source_commit=SOURCE, binary_sha256=cap['binary_sha256'],
                scope=str(scope), stop=cap['stop'], stderr_sha256=hashlib.sha256(raw).hexdigest(),
                requested_gates={key: value for key, value in cap['launch_environment'].items() if key.startswith('LLAMA_')},
                native_bank_readbacks=banks, recorder=recorder, placement=placement, mapper=mapper,
                legacy_predictor=marker(log, 'expert_demand_predictor'), legacy_cache=marker(log, 'expert_weight_cache'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scope', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    report = readback(args.scope.resolve(strict=True))
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
