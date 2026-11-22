"""Bounded, explanation-only native Strata and Nsight evidence analysis.

No process launch, arbitrary file reads, or authority expansion. Execution is
submitted through the existing host lab adapter with a fixed observer mode.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import re
import shutil

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 10000
REPORTS = {'kernels', 'cuda_api', 'os_runtime', 'memcpy'}
GAPS = [
    'Request/token/layer/expert keyed predictions and actual selected experts, with top-k and predictor revision.',
    'Monotonic prediction, enqueue, read-start, read-complete and first-demand timestamps on a shared clock.',
    'Requested/completed/consumed bytes, residency at demand, inflight join and duplicate-read identity.',
    'Critical-path demand wait separated from overlapped read/compute time; fixed prefill/decode boundaries.',
    'Coverage and dropped-event counters, bounded sampling policy and observer overhead calibration.',
]


def _text(value):
    if not isinstance(value, str) or len(value.encode()) > MAX_BYTES:
        raise ValueError('Each profile artifact must be UTF-8 text of at most 8 MiB')
    return value


def _number(value):
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid profile numeric field') from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError('Profile numbers must be finite and nonnegative')
    return result


def native_stages(stderr):
    """Parse DS4_PROF prompt tables without counting their coarse total twice.

    Tables are emitted once per prompt and reset by the engine. The expert
    kernel subtable and CPU-lane per-call averages are deliberately separate.
    """
    _text(stderr)
    totals = {}
    tables = 0
    for line in stderr.splitlines():
        match = re.fullmatch(r'ds4 prof\s+(.+?)\s+([\d.]+) ms\s+([\d.]+)%\s*', line)
        if not match:
            continue
        name, raw_ms, percent = match.groups()
        ms = _number(raw_ms)
        if _number(percent) > 100:
            raise ValueError('Invalid native stage percentage')
        totals[name] = totals.get(name, 0) + ms
        if name == 'between layers':
            tables += 1
    disabled = [line[:300] for line in stderr.splitlines() if 'ds4: profiling disabled:' in line][:10]
    total = sum(totals.values())
    stages = [dict(stage=name, total_ms=round(ms, 3),
                   share=ms / total if total else None)
              for name, ms in sorted(totals.items(), key=lambda row: row[1], reverse=True)]
    return dict(status='invalid' if disabled else ('measured' if tables else 'not_measured'),
                phase='prefill', clock='summed per-device CUDA event intervals',
                tables=tables, stages=stages, profiling_errors=disabled,
                candidate_bottleneck=stages[0]['stage'] if tables and stages and total and not disabled else None,
                limitation='GPU interval attribution includes expert waits; summed device intervals are not wall time or proof of I/O causality.')


def stream_counters(stderr):
    """Read ordinary prompt streaming counters, without DS4_PROF or a rerun.

    Each record retains its device/prompt scope. Busy-worker and staging
    durations can overlap elapsed prompt time and must never be added to it.
    """
    _text(stderr)
    number = r'([^\s,;()]+)'
    pattern = re.compile(
        r'ds4 prompt stream, CUDA(\d+): (\d+) tokens in ' + number +
        r' ms; (\d+) experts streamed: (\d+) from the files \(' + number +
        r' GB, ' + number + r' GB/s: ' + number +
        r' GB from the disk unbuffered, ' + number +
        r' GB through the page cache\), (\d+) from RAM \(' + number + r' GB\)'
        r'(?:, (\d+) again from the layer cache \(layer-major, (\d+) chunks, ' + number + r' GB of RAM\))?'
        r'; (\d+) likely ones queued early, (\d+) of them unpicked; the compute waited ' + number +
        r' ms for reads(?:; io threads busy ' + number + r' ms, copy_ahead staging ' + number +
        r' ms, DMA issues ' + number + r' ms, slot waits ' + number + r' ms)?')
    records, unparsed = [], []
    matched_lines = 0
    for line in stderr.splitlines():
        if not line.startswith('ds4 prompt stream, '):
            continue
        matched_lines += 1
        if matched_lines > MAX_ROWS:
            raise ValueError('Streaming counters exceed 10000 rows')
        if len(line) > 16384:
            raise ValueError('Streaming counter row exceeds 16 KiB')
        match = pattern.fullmatch(line)
        if not match:
            if len(unparsed) < 10:
                unparsed.append(line[:300])
            continue
        (device, tokens, elapsed, streamed, files, file_gb, file_rate, direct_gb,
         buffered_gb, ram, ram_gb, layer_cache, chunks, cache_gb, queued,
         unpicked, waited, busy, staging, dma, slots) = match.groups()
        counts = [int(v) for v in (streamed, files, ram, layer_cache or '0', queued, unpicked)]
        if counts[0] != sum(counts[1:4]) or counts[5] > counts[4]:
            raise ValueError('Inconsistent streaming expert counters')
        elapsed_ms, waited_ms = _number(elapsed), _number(waited)
        wait_ratio = waited_ms / elapsed_ms if elapsed_ms else None
        if wait_ratio is not None and not math.isfinite(wait_ratio):
            raise ValueError('Streaming wait ratio exceeds finite numeric bounds')
        record = dict(device=int(device), tokens=int(tokens), prompt_elapsed_ms=elapsed_ms,
                      experts_streamed=counts[0], file_experts=counts[1], ram_experts=counts[2],
                      layer_cache_experts=counts[3] if layer_cache is not None else None,
                      file_payload_gb=_number(file_gb),
                      reported_file_payload_gb_per_prompt_second=_number(file_rate),
                      reported_unbuffered_file_gb=_number(direct_gb),
                      reported_page_cache_file_gb=_number(buffered_gb), ram_payload_gb=_number(ram_gb),
                      layer_cache_chunks=int(chunks) if chunks is not None else None,
                      layer_cache_ram_gb=_number(cache_gb) if cache_gb is not None else None,
                      early_queued_experts=counts[4], early_unpicked_experts=counts[5],
                      compute_read_wait_ms=waited_ms,
                      read_wait_to_prompt_elapsed_ratio=wait_ratio)
        for key, value in (('io_worker_busy_ms', busy), ('copy_ahead_staging_ms', staging),
                           ('dma_issue_ms', dma), ('slot_wait_ms', slots)):
            record[key] = _number(value) if value is not None else None
        records.append(record)
    return dict(status=('partial' if records else 'unparsed') if unparsed else
                ('measured' if records else 'not_measured'), phase='prefill', records=records,
                unparsed_rows=matched_lines - len(records), unparsed_examples=unparsed,
                limitation='Per-prompt/device native counters only. Worker busy, copy, DMA and slot intervals overlap; '
                           'never sum them into wall time or across devices. File payload/elapsed rate is not disk bandwidth; '
                           'page-cache file bytes do not prove physical reads. Rounded counters do not establish predictor '
                           'recall, on-time readiness, duplicate reads, wasted bytes or a performance gain.')


def nsight_csv(text):
    """Parse one report family; reports overlap and are never added together."""
    _text(text)
    rows = csv.DictReader(io.StringIO(text))
    if not {'Total Time (ns)'}.issubset(rows.fieldnames or []):
        raise ValueError('Nsight CSV requires Total Time (ns) column')
    out = []
    for index, row in enumerate(rows):
        if index >= MAX_ROWS:
            raise ValueError('Nsight CSV exceeds 10000 rows')
        name = row.get('Name') or row.get('Operation')
        if not name:
            raise ValueError('Nsight CSV requires a Name or Operation')
        count = _number(row.get('Instances', row.get('Num Calls', row.get('Count', 0))))
        if not count.is_integer():
            raise ValueError('Nsight count must be an integer')
        out.append(dict(name=name[:240], total_ms=_number(row['Total Time (ns)']) / 1e6,
                        count=int(count)))
    total = sum(row['total_ms'] for row in out)
    top = sorted(out, key=lambda row: row['total_ms'], reverse=True)[:10]
    return dict(total_ms=total, entries=len(out), top=top,
                limitation='Aggregated durations can overlap; this report cannot establish a critical path or phase attribution.')


def analyze(artifacts):
    if not isinstance(artifacts, dict) or not artifacts or set(artifacts) - (REPORTS | {'stderr'}):
        raise ValueError('Supply stderr and/or recognized Nsight report families')
    out = dict(traced=True, scoring_eligible=False, performance_gain='not_established',
               observer_overhead='unknown; compare matched observer-off/on runs before interpretation',
               native=native_stages(artifacts.get('stderr', '')),
               ordinary_stream=stream_counters(artifacts.get('stderr', '')),
               nsight={name: nsight_csv(value) for name, value in artifacts.items() if name in REPORTS},
               missing_expert_prediction_evidence=GAPS,
               expert_prediction=dict(recall_at_k=None, ready_at_demand_ratio=None,
                                      demand_wait_ms=None, wasted_bytes=None, duplicate_bytes=None))
    out['source_sha256'] = {key: hashlib.sha256(_text(value).encode()).hexdigest()
                            for key, value in artifacts.items()}
    return out


def plan():
    return dict(status='proposal', run_config={'profile': 'strata-native'},
                submit_via='factory.lab_client.submit', observer_environment={'DS4_PROF': '1'},
                limits='Inherit immutable contract timeout, replay, CPU/memory, host guard and existing lease/guardian.',
                scoring_eligible=False, performance_gain='not_established',
                tools={name: dict(path=shutil.which(name), execution_tested=False)
                       for name in ('nsys', 'ncu')},
                overhead=dict(native='CUDA events, host accounting and synchronization perturb timing; cost unknown.',
                              nsys='CUDA/OS runtime tracing can perturb scheduling; not enabled by this native mode.',
                              ncu='Kernel replay/serialization can dominate timing; not enabled by this mode.'),
                next_evidence=['Retain full stderr and lifecycle/boundary artifacts from a native profile run.',
                               'Analyze phase attribution, then run matched uninstrumented repeats for speed evidence.'],
                missing_expert_prediction_evidence=GAPS)


def dispatch(store, task_id, capability, inputs):
    from .api import fields
    if capability == 'plan':
        fields(inputs, {})
        result = plan()
        refs = []
    elif capability == 'analyze':
        fields(inputs, {'artifacts'}, {'artifacts'})
        refs_by_kind = inputs['artifacts']
        if not isinstance(refs_by_kind, dict) or not refs_by_kind or set(refs_by_kind) - (REPORTS | {'stderr'}):
            raise ValueError('Invalid profile artifact map')
        if any(not isinstance(ref, str) or not ref for ref in refs_by_kind.values()):
            raise ValueError('Artifact references must be nonempty strings')
        result = analyze({kind: store.artifact_bytes(task_id, ref).decode('utf-8')
                          for kind, ref in refs_by_kind.items()})
        refs = list(refs_by_kind.values())
    else:
        raise ValueError('Unknown deep_profile capability')
    evidence = store.append_observation(task_id, dict(kind='deep_profile_' + capability,
        values=result, source_artifacts=refs, limitations='Explanation only; no scoring or predicted benefit.'))
    return dict(analysis=result, evidence=evidence)
