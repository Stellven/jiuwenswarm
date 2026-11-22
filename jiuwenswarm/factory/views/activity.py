"""Normalize recorded engine and factory evidence without running engine tools.

Unknown measurements are None throughout. Teardown totals are never distributed
over tokens, and independent trace sessions are never pooled for recall/timing.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile

from ..redact import sanitize

SCHEMA = 'expert_activity/1'
TRACE_SCHEMA = 'expert_trace/2'
READINESS = ('resident', 'prefetched_done', 'inflight', 'queued', 'missing', 'unknown')
PHASES = ('load', 'prompt', 'decode')
TRACE_NAMES = ('expert_trace.jsonl', 'expert-trace.jsonl', 'expert_trace.csv',
               'expert-trace.csv', 'trace.jsonl', 'trace.csv')
KV = re.compile(r'\b([a-zA-Z_]\w*)=([^\s]+)')


def _number(value, integer=False):
    if value is None or isinstance(value, bool) or value in ('', 'UNKNOWN', 'unknown', 'null'):
        return None
    try:
        number = float(value)
        if not math.isfinite(number) or number < 0:
            return None
        if integer:
            return int(value) if not isinstance(value, float) or value.is_integer() else None
        return number
    except (ValueError, TypeError, OverflowError):
        return None


def _value(value):
    integer = _number(value, integer=True)
    return integer if integer is not None else (_number(value) if _number(value) is not None else value)


def _overhead(mode, declared=None):
    declared = declared if isinstance(declared, dict) else {}
    return dict(mode=declared.get('mode') or mode,
                measured_ratio=_number(declared.get('measured_ratio')),
                evidence_id=declared.get('evidence_id'))


def _source(path, content, kind, coverage, overhead=None):
    raw = content.encode() if isinstance(content, str) else content
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), kind=kind,
                coverage=coverage, overhead=overhead or _overhead('stats lines: negligible emission'))


def parse_stderr(text, source='stderr.txt'):
    """Read exact engine key=value counters, retaining line provenance/snapshots.

    Differing snapshots of one subsystem are ambiguous (multiple contexts), so
    their aggregate is UNKNOWN. Repeated identical effective config lines are OK.
    """
    snapshots = defaultdict(list)
    configs, timings, notes = [], {}, []
    model = dict(n_layers=None, n_expert_used=None)
    placement = []
    for line_no, line in enumerate(text.splitlines(), 1):
        config = re.search(r'expert_config: effective\b.*', line)
        if config:
            configs.append(dict(line=line_no, text=config[0], values={k: _value(v) for k, v in KV.findall(config[0])}))
        match = re.search(r'expert_(fill|pregate|readiness): stats\b(.*)', line)
        if match:
            snapshots[match[1]].append(dict(source=source, line=line_no,
                values={k: _value(v) for k, v in KV.findall(match[2])}))
        for label, name in [('n_layer', 'n_layers'), ('n_expert_used', 'n_expert_used')]:
            m = re.search(r'\b' + label + r'\s*=\s*(\d+)\b', line)
            if m:
                model[name] = int(m[1])
        if 'offloaded ' in line or ('expert_fill: active' in line):
            placement.append(dict(line=line_no, text=line.strip()))
        phase = ('prompt' if 'prompt eval time' in line else
                 'decode' if re.search(r'\beval time\s*=', line) else
                 'load' if re.search(r'\bload time\s*=', line) else None)
        if phase:
            duration = re.search(r'time\s*=\s*([\d.]+)\s*ms', line)
            tokens = re.search(r'ms\s*/\s*(\d+)\s*(?:tokens|runs)', line)
            if duration:
                timings[phase] = dict(duration_ns=round(float(duration[1]) * 1_000_000),
                                      tokens=int(tokens[1]) if tokens else None,
                                      source=f'{source}:{line_no}')
    result = dict(snapshots=dict(snapshots), config_lines=configs, timings=timings,
                  model=model, placement=placement, notes=notes)
    for kind in ('fill', 'pregate', 'readiness'):
        rows = snapshots[kind]
        unique = {json.dumps(r['values'], sort_keys=True) for r in rows}
        result[kind] = rows[0]['values'] if len(unique) == 1 else None
        if len(unique) > 1:
            notes.append(f'Multiple differing {kind} teardown snapshots; aggregate UNKNOWN; not summed across contexts.')
    unique_configs = {r['text'] for r in configs}
    result['effective_config_line'] = configs[0]['text'] if len(unique_configs) == 1 else None
    result['effective_config'] = configs[0]['values'] if len(unique_configs) == 1 else None
    if len(unique_configs) > 1:
        notes.append('Multiple effective configs; run-to-context association UNKNOWN.')
    result['source'] = source
    return result


def _ids(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.split()
    if not isinstance(value, (list, tuple)):
        raise ValueError('IDs must be an array or space-separated integers')
    ids = [_number(v, integer=True) for v in value]
    if None in ids or len(set(ids)) != len(ids):
        raise ValueError('IDs must be unique nonnegative integers')
    return ids


def _event(row, source, line, default_run):
    phase = row.get('phase') or 'unknown'
    if phase not in ('prompt', 'decode', 'unknown'):
        raise ValueError('invalid expert phase')
    token = _number(row.get('token_idx'), integer=True)
    layer = _number(row.get('layer'), integer=True)
    if token is None or layer is None:
        raise ValueError('token_idx and layer must be nonnegative integers')
    selected = _ids(row.get('selected_ids', row.get('selected')))
    predicted = _ids(row.get('predicted_ids', row.get('predicted')))
    if selected == []:
        raise ValueError('empty selected IDs')
    readiness = row.get('readiness')
    if isinstance(readiness, str):
        try:
            readiness = json.loads(readiness)
        except ValueError:
            readiness = readiness.split()
    by_id = {}
    if isinstance(readiness, dict):
        by_id = {str(k): v for k, v in readiness.items()}
    elif isinstance(readiness, list):
        for index, item in enumerate(readiness):
            if isinstance(item, dict):
                by_id[str(item.get('expert_id'))] = item
            elif selected is not None and index < len(selected):
                by_id[str(selected[index])] = item
    states = []
    for expert in selected or []:
        item = by_id.get(str(expert))
        item = item if isinstance(item, dict) else {'class': item}
        state = item.get('class')
        states.append(dict(expert_id=expert, **{'class': state if state in READINESS else 'unknown'},
                           required_bytes=_number(item.get('required_bytes'), integer=True),
                           resident_bytes=_number(item.get('resident_bytes'), integer=True)))
    spec = row.get('speculative') or {}
    if isinstance(spec, str):
        spec = json.loads(spec)
    if not isinstance(spec, dict):
        raise ValueError('speculative must be an object')
    event = dict(run_id=str(row.get('run_id', row.get('run', default_run))), phase=phase,
                 token_idx=token, layer=layer, selected_ids=selected, predicted_ids=predicted,
                 prediction_source=row.get('prediction_source'), readiness=states,
                 speculative={key: _number(spec.get(key), integer=True) for key in
                     ('issued_bytes', 'read_bytes', 'used_bytes', 'wasted_bytes', 'timely_bytes', 'late_bytes')},
                 source=f'{source}:{line}')
    event['speculative']['unused_scope'] = spec.get('unused_scope')
    for key in ('demand_read_bytes', 'demand_wait_ns', 'arrival_ns', 'fill_end_ns',
                'join_waits', 'join_wait_ns', 'join_bytes'):
        event[key] = _number(row.get(key), integer=True)
    if event['arrival_ns'] is not None and event['fill_end_ns'] is not None and event['fill_end_ns'] < event['arrival_ns']:
        raise ValueError('fill ends before arrival')
    return event


def parse_trace(text, source='expert_trace.jsonl', *, run_id='run', trace_run=None):
    """Convert v2 JSONL / selection CSV, preserving absent measurements as None.

    Invalid/truncated rows are excluded with explicit coverage notes. An unknown
    version is an error, to prevent accidentally interpreting a different wire.
    """
    events, tokens, metadata, notes, seen = [], [], {}, [], set()
    if not text.strip():
        return dict(events=[], tokens=[], metadata={}, notes=['Empty trace; per-token data UNKNOWN.'],
                    format=None, source=source, sessions=[])
    is_json = text.lstrip().startswith('{')
    if is_json:
        rows = []
        for line, raw in enumerate(text.splitlines(), 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
                if not isinstance(row, dict):
                    raise ValueError('record must be an object')
                if row.get('schema', TRACE_SCHEMA) != TRACE_SCHEMA:
                    raise ValueError('unsupported trace schema')
                rows.append((line, row))
            except ValueError as exc:
                if str(exc) == 'unsupported trace schema':
                    raise
                notes.append(f'{source}:{line}: invalid/truncated JSON record excluded.')
    else:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or not {'token_idx', 'layer', 'selected'}.issubset(reader.fieldnames):
            raise ValueError('Trace CSV requires token_idx, layer, selected columns')
        rows = [(line, dict(row)) for line, row in enumerate(reader, 2)]
        notes.append('Selection CSV: readiness, byte attribution and token timing UNKNOWN. Phase uses ubatch size; one-token prompts may be labelled decode.')
        notes.append('P12 token indices count processed ubatch tokens, including CLI warmup, not sequence positions. Output-pruned prompt rows may be absent; missing cells UNKNOWN.')
        if 'predicted' in reader.fieldnames:
            notes.append('CSV prediction source is not recorded; current llama-opt emitter records pregate distance 1 (source inferred from inspected code).')
        notes.append('CSV session IDs are opaque; matching a session to surrounding teardown stats is not established by timestamp.')
    excluded = 0
    for line, row in rows:
        session = str(row.get('run_id', row.get('run', run_id)))
        if trace_run is not None and session != str(trace_run):
            excluded += 1
            continue
        kind = row.get('type', 'expert')
        if kind == 'meta':
            metadata[session] = row
            continue
        try:
            if kind == 'token':
                token = _number(row.get('token_idx'), integer=True)
                if token is None or row.get('phase') not in ('prompt', 'decode'):
                    raise ValueError('invalid token key')
                start, end = (_number(row.get(key), integer=True) for key in ('start_ns', 'end_ns'))
                duration = _number(row.get('duration_ns'), integer=True)
                if start is not None and end is not None:
                    if end < start:
                        raise ValueError('token ends before start')
                    duration = end - start
                record = dict(run_id=session, phase=row['phase'], token_idx=token,
                              start_ns=start, end_ns=end, duration_ns=duration,
                              demand_wait_ns=_number(row.get('demand_wait_ns'), integer=True),
                              source=f'{source}:{line}')
                key = (kind, session, row['phase'], token)
                target = tokens
            elif kind == 'expert':
                record = _event(row, source, line, run_id)
                key = (kind, session, record['phase'], record['token_idx'], record['layer'])
                target = events
            else:
                raise ValueError('unknown record type')
            if key in seen:
                raise ValueError('duplicate key')
            seen.add(key)
            target.append(record)
        except (ValueError, TypeError, KeyError):
            notes.append(f'{source}:{line}: invalid/duplicate trace record excluded; coverage incomplete.')
    if excluded:
        notes.append(f'--trace-run selected {trace_run}; {excluded} other-session records excluded.')
    if not events:
        notes.append('No expert trace events available; activity map UNKNOWN.')
    sessions = sorted({e['run_id'] for e in events})
    if len(sessions) > 1:
        notes.append('Appended trace sessions remain separate. Teardown stats are not attributed across sessions.')
    return dict(events=events, tokens=tokens, metadata=metadata, notes=notes,
                format=TRACE_SCHEMA if is_json else 'selection-csv/1', source=source, sessions=sessions)


def _sum_known(values):
    values = list(values)
    return sum(values) if values and all(v is not None for v in values) else None


def _predictions(events):
    groups = defaultdict(list)
    for event in events:
        groups[(event['run_id'], event['phase'], event['layer'])].append(event)
    result = []
    for (run, phase, layer), rows in sorted(groups.items()):
        comparable = [r for r in rows if r['selected_ids'] is not None and r['predicted_ids'] is not None]
        actual = sum(len(r['selected_ids']) for r in comparable)
        predicted = sum(len(r['predicted_ids']) for r in comparable)
        hits = sum(len(set(r['selected_ids']) & set(r['predicted_ids'])) for r in comparable)
        states = [x['class'] for r in rows for x in r['readiness'] if r['predicted_ids'] is not None
                  and x['expert_id'] in r['predicted_ids']]
        result.append(dict(run_id=run, phase=phase, layer=layer, records=len(rows),
            compared_records=len(comparable), selected_count=actual if comparable else None,
            predicted_count=predicted if comparable else None, hits=hits if comparable else None,
            recall=hits / actual if actual else None, precision=hits / predicted if predicted else None,
            timely_selected=sum(s in ('resident', 'prefetched_done') for s in states) if states and 'unknown' not in states else None,
            late_selected=sum(s in ('inflight', 'queued', 'missing') for s in states) if states and 'unknown' not in states else None,
            speculative={k: _sum_known(r['speculative'][k] for r in rows) for k in
                ('issued_bytes', 'read_bytes', 'used_bytes', 'wasted_bytes', 'timely_bytes', 'late_bytes')},
            unused_scopes=sorted({r['speculative']['unused_scope'] for r in rows if r['speculative']['unused_scope']}),
            prediction_sources=[r['prediction_source'] for r in rows if r['prediction_source'] is not None][:3]))
    return result


def _timeline(trace, model):
    groups = defaultdict(list)
    for event in trace['events']:
        if event['phase'] == 'decode':
            groups[(event['run_id'], event['token_idx'])].append(event)
    clocks = {(r['run_id'], r['token_idx']): r for r in trace['tokens'] if r['phase'] == 'decode'}
    result = []
    for run, token in sorted(groups.keys() | clocks.keys()):
        rows = groups[(run, token)]
        expected = _number(trace['metadata'].get(run, {}).get('n_layers'), integer=True) or model.get('n_layers')
        complete = expected is not None and {r['layer'] for r in rows} == set(range(expected))
        measured = [r['demand_wait_ns'] for r in rows if r['demand_wait_ns'] is not None]
        clock = clocks.get((run, token), {})
        wait = clock.get('demand_wait_ns')
        if wait is None and complete:
            wait = _sum_known(r['demand_wait_ns'] for r in rows)
        duration = clock.get('duration_ns')
        rest = duration - wait if duration is not None and wait is not None and duration >= wait else None
        result.append(dict(run_id=run, token_idx=token, demand_wait_ns=wait,
            measured_layer_wait_ns=sum(measured) if measured else None,
            measured_layers=len(measured), expected_layers=expected, token_duration_ns=duration,
            rest_ns=rest, rest_attribution='inferred residual wall time; no CPU/GPU compute attribution',
            source=clock.get('source') or (rows[0]['source'] if rows else None),
            timing_consistent=not (duration is not None and wait is not None and duration < wait)))
    return result


def _image_id(value):
    if isinstance(value, dict):
        value = value.get('id', value.get('image_id'))
    return value if isinstance(value, str) and re.fullmatch(r'sha256:[0-9a-fA-F]{64}', value) else None


def _placement(result, stats, source):
    argv = result.get('argv') or []
    cmoe = '-cmoe' in argv or '--cpu-moe' in argv
    gpu_log = next((x for x in stats['placement'] if re.search(r'offloaded (\d+)/\1 layers to GPU', x['text'])), None)
    return dict(experts='CPU (inferred from -cmoe)' if cmoe else None,
                non_expert='GPU (inferred from full layer offload log)' if cmoe and gpu_log else None,
                source=[source] + ([f"{stats['source']}:{gpu_log['line']}"] if gpu_log else []),
                note='Placement is inferred from argv/logs, not timed backend attribution. Page-cache residency does not place experts on GPU.')


def build_activity(stats=None, trace=None, *, metadata=None, sources=(), result=None,
                   summary=None, threads=None, run_id='run', task_id=None, changes=(), mode='replay'):
    """Build expert_activity/1. All input data stays detached from the store."""
    metadata, result, summary = metadata or {}, result or {}, summary or {}
    stats = stats or parse_stderr('')
    trace = trace or dict(events=[], tokens=[], metadata={}, notes=[], format=None, source=None, sessions=[])
    fill, pregate, readiness = (stats.get(k) or {} for k in ('fill', 'pregate', 'readiness'))
    trace_meta = next(iter(trace['metadata'].values())) if len(trace['metadata']) == 1 else {}
    image = metadata.get('image_id') or trace_meta.get('image_id') or result.get('image_id') or result.get('image')
    phases = {}
    fill_source = next((f"{r['source']}:{r['line']}" for r in stats['snapshots'].get('fill', [])
                        if r['values'] == stats.get('fill')), None)
    summary_source = next((s['path'] for s in sources if s['kind'] == 'run-summary'), None)
    for phase in PHASES:
        timing = stats['timings'].get(phase, {})
        duration = timing.get('duration_ns')
        if duration is None:
            ms = summary.get({'load': 'load_ms', 'prompt': 'prompt_ms_total', 'decode': 'eval_ms_total'}[phase])
            duration = round(ms * 1_000_000) if _number(ms) is not None else None
        declared = trace_meta.get('phase_summary', {}).get(phase, {})
        phase_events = [e for e in trace['events'] if e['phase'] == phase]
        phases[phase] = dict(duration_ns=duration, tokens=timing.get('tokens') if timing.get('tokens') is not None else
            (_number(summary.get('eval_tokens'), integer=True) if phase == 'decode' else None),
            demand_read_bytes=fill.get(phase + '_bytes_read'),
            demand_wait_ns=fill.get(phase + '_fill_wall_ns'),
            demand_calls=fill.get(phase + '_calls'),
            trace_records=len(phase_events), trace_tokens=len({(e['run_id'], e['token_idx']) for e in phase_events}),
            coverage='aggregate counters only' if not phase_events else 'observed trace records; see sampling',
            source=timing.get('source') or summary_source or trace.get('source'),
            sources=dict(duration_ns=timing.get('source') or summary_source, tokens=timing.get('source') or summary_source,
                         demand_read_bytes=fill_source, demand_wait_ns=fill_source))
        for key in ('duration_ns', 'tokens', 'demand_read_bytes', 'demand_wait_ns'):
            if phases[phase][key] is None:
                phases[phase][key] = _number(declared.get(key), integer=True)
                if phases[phase][key] is not None:
                    phases[phase]['sources'][key] = trace.get('source')
        if not phase_events and all(phases[phase][key] is None for key in ('duration_ns', 'tokens', 'demand_read_bytes', 'demand_wait_ns')):
            phases[phase]['coverage'] = 'UNKNOWN: no phase measurement'
    predictions = _predictions(trace['events'])
    notes = list(stats['notes']) + list(trace['notes']) + list(metadata.get('notes') or [])
    if not trace['events']:
        notes.append('aggregate, no per-token trace — selected IDs, per-layer recall, readiness and per-token waits UNKNOWN.')
    notes.extend([
        'Engine decode counters use n_tokens == 1; a one-token prompt may be included. Load, prompt and decode totals are kept separate.',
        'hit_done/pred_done are completion buckets, not proof of residency at arrival; no readiness cells are inferred from aggregates.',
        'Bytes are pread volume, not physical device traffic. Cancelled request bytes are not wasted reads.',
        'Fill pread/wait counters cover explicit demand fill only. Zero prompt fill calls do not establish zero fault-driven I/O or zero compute stalls.',
        'Target-arrival unused predictions may be reused later. Lifetime unused speculative bytes remain UNKNOWN unless end_of_run tracking is supplied.',
    ])
    if (stats.get('effective_config') or {}).get('diag') == 1:
        notes.append('DIAG=1 perturbs timing (extra graph cuts, residency probes and fault counters).')
    if summary.get('traced') or (result.get('traced')):
        notes.append('Profiled run: instrumentation perturbs timing; not an untraced performance result.')
    synthetic = metadata.get('origin') == 'synthetic' or any(m.get('origin') == 'synthetic' for m in trace['metadata'].values())
    if synthetic:
        mode = 'synthetic'
    layers = sorted({e['layer'] for e in trace['events']})
    model = dict(stats['model'])
    for key in model:
        model[key] = model[key] or _number(metadata.get(key, trace_meta.get(key)), integer=True)
    doc = dict(schema=SCHEMA,
        provenance=dict(run_id=str(metadata.get('run_id') or run_id), task_id=task_id, mode=mode,
            origin='synthetic' if synthetic or mode == 'synthetic' else 'recorded evidence',
            image_id=_image_id(image), image_ref=metadata.get('image_ref') or trace_meta.get('image_ref') or result.get('image'),
            effective_config_line=stats['effective_config_line'] or metadata.get('effective_config_line') or trace_meta.get('effective_config_line'),
            effective_config=stats['effective_config'], source_files=list(sources),
            phase_coverage={p: {k: phases[p][k] for k in ('coverage', 'trace_records', 'trace_tokens', 'source')} for p in PHASES},
            sampling=dict(stats='teardown totals; no per-token interpolation; ambiguous contexts not summed',
                trace=metadata.get('sampling') or trace_meta.get('sampling') or {'mode': 'unknown'},
                phase_definition=trace_meta.get('phase_definition', 'ubatch_size for existing engine counters/CSV'),
                notes='All available valid trace rows retained. Missing cells UNKNOWN; observed rows do not prove full coverage.'),
            overhead=_overhead('offline view: outside engine timing window; source instrumentation declared separately'),
            placement=_placement(result, stats, next((s['path'] for s in sources if s['kind'] == 'run-result'), 'argv UNKNOWN'))),
        model=model, stats=stats, phases=phases,
        totals=dict(demand_read_bytes=fill.get('bytes_read'), speculative_read_bytes=pregate.get('async_bytes_read'),
            speculative_issued_bytes=None, speculative_used_bytes=None,
            speculative_unused_target_bytes=readiness.get('decode_wasted_async_bytes'),
            speculative_unused_lifetime_bytes=None, duplicate_demand_bytes=readiness.get('decode_duplicate_demand_bytes'),
            demand_wait_ns=fill.get('demand_wait_ns_total', fill.get('total_fill_wall_ns')),
            demand_wait_ns_per_token=fill.get('demand_wait_ns_per_token'),
            join_waits=pregate.get('join_waits'), join_wait_ns=pregate.get('join_wait_ns'), join_bytes=pregate.get('join_bytes')),
        activity=dict(status='trace' if trace['events'] else 'unknown', events=trace['events'], layers=layers,
            sessions=trace['sessions'], metadata=trace['metadata'], trace_format=trace['format'], source=trace['source']),
        predictions=predictions, timeline=_timeline(trace, model), changes=list(changes),
        threads=threads, notes=notes)
    return sanitize(doc)


def _json_file(path, sources, kind):
    if not path.is_file():
        return {}
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f'{path.name} must be a JSON object')
    sources.append(_source(path, raw, kind, 'recorded run metadata', _overhead('offline metadata; collection cost UNKNOWN')))
    return value


def _stats_overhead(stats):
    config = stats.get('effective_config') or {}
    modes = ['stats lines: negligible emission']
    if config.get('readiness') == 1:
        modes.append('READINESS instrumentation: probes unmeasured; operator A/B required')
    if config.get('diag') == 1:
        modes.append('DIAG instrumentation: timing perturbed; unmeasured')
    return _overhead('; '.join(modes))


def load_run(run_dir, *, trace_path=None, trace_run=None, mode='replay'):
    directory = Path(run_dir).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError('Expected a run directory')
    sources = []
    metadata = _json_file(directory / 'view-meta.json', sources, 'view-metadata')
    result = _json_file(directory / 'result.json', sources, 'run-result')
    summary = _json_file(directory / 'summary.json', sources, 'run-summary')
    threads = _json_file(directory / 'threads.summary.json', sources, 'thread-summary')
    if threads:
        sources[-1]['coverage'] = threads.get('phase_window') or 'thread sampling coverage UNKNOWN'
        sources[-1]['overhead'] = _overhead('external thread sampler; self CPU is not engine overhead A/B')
    stderr_path = directory / 'stderr.txt'
    raw = stderr_path.read_bytes() if stderr_path.is_file() else b''
    stats = parse_stderr(raw.decode(errors='replace'), str(stderr_path))
    if stderr_path.is_file():
        sources.append(_source(stderr_path, raw, 'engine-stats', 'load/prompt/decode teardown counters; no per-event data', _stats_overhead(stats)))
    candidates = [directory / name for name in TRACE_NAMES if (directory / name).is_file()]
    config_trace = (stats['effective_config'] or {}).get('trace')
    if isinstance(config_trace, str) and config_trace != '(unset)':
        local = directory / Path(config_trace).name
        if local.is_file() and local not in candidates:
            candidates.append(local)
    if trace_path is not None:
        trace_path = Path(trace_path).expanduser().resolve()
    elif len(candidates) == 1:
        trace_path = candidates[0]
    elif len(candidates) > 1:
        raise ValueError('Multiple trace files; select one with --trace')
    trace = None
    if trace_path is not None:
        raw_trace = trace_path.read_bytes()
        trace = parse_trace(raw_trace.decode(errors='replace'), str(trace_path), run_id=metadata.get('run_id', directory.name), trace_run=trace_run)
        declared = metadata.get('overhead') or (next(iter(trace['metadata'].values())).get('overhead') if len(trace['metadata']) == 1 else None)
        sources.append(_source(trace_path, raw_trace, 'expert-trace', 'observed rows only; see sampling and converter notes',
                               _overhead('trace: operator A/B required; unmeasured', declared)))
    run_id = f'{directory.parent.name}/{directory.name}'
    return build_activity(stats, trace, metadata=metadata, sources=sources, result=result,
                          summary=summary, threads=threads or None, run_id=run_id, mode=mode)


def _component(value):
    return str(value).removeprefix('factory.components.') if value else None


def _files(record):
    value = next((record[k] for k in ('files_changed', 'changed_files', 'files') if record.get(k)), None)
    if isinstance(value, dict):
        return sorted(value)
    if isinstance(value, list):
        return [v.get('path') if isinstance(v, dict) else str(v) for v in value]
    nested = [path for p in record.get('applied_patches', []) if isinstance(p, dict)
              for path in (_files(p) or [])]
    if nested:
        return sorted(set(nested))
    return None


def build_changes(records):
    """Join only explicit evidence / attempt / image references, never time proximity."""
    decisions = records.get('decisions', [])
    observations = records.get('observations', [])
    attempts = records.get('attempts', [])
    evaluations = records.get('evaluations', [])
    indexed = {r[key]: r for rows, key in [(decisions, 'decision_id'), (observations, 'obs_id'),
               (attempts, 'attempt_id'), (evaluations, 'eval_id')] for r in rows}
    roots = [r for r in decisions if r.get('action', {}).get('component')]
    roots += [r for r in observations if r.get('values', {}).get('component')
              and r.get('kind') in ('component_applied', 'integration_result')]
    result = []
    for root in sorted(roots, key=lambda r: (r.get('created', 0), r.get('rev', 0))):
        action = root.get('action') or root.get('values', {})
        component = _component(action.get('component'))
        refs = list(root.get('evidence_ids', []))
        linked = [root]
        pending = list(refs)
        pending += [action[k] for k in ('attempt_id', 'build_attempt_id') if isinstance(action.get(k), str)]
        visited = set()
        while pending:
            key = pending.pop()
            if key in visited or key not in indexed:
                continue
            visited.add(key)
            r = indexed[key]
            linked.append(r)
            pending.extend(r.get('evidence_ids', []))
            attempt_id = r.get('host_run', {}).get('attempt_id')
            if attempt_id:
                pending.append(attempt_id)
            observation_id = r.get('inputs', {}).get('observation_id')
            if observation_id:
                pending.append(observation_id)
            # A/B admissions carry separate base and candidate build identities.
            # Follow only candidate for the component's resulting source/image.
            request = r.get('request') or {}
            admission = request.get('admission') or request.get('admissions', {}).get('candidate') or {}
            if admission.get('build_attempt_id'):
                pending.append(admission['build_attempt_id'])
        # A build result is linked by its explicit build attempt, not its date.
        linked_attempts = {r.get('attempt_id') for r in linked if r.get('attempt_id')}
        linked += [o for o in observations if o not in linked and o.get('host_run', {}).get('attempt_id') in linked_attempts]
        commit, files, image_id, effective, engagement, ab = None, None, None, None, None, None
        for r in linked:
            payloads = [r.get('action', {}), r.get('values', {}), r.get('request', {}), r.get('inputs', {})]
            for payload in payloads:
                source = payload.get('source') or {}
                if isinstance(source, dict):
                    commit = commit or source.get('commit') or payload.get('source_commit')
                    files = files or _files(source) or _files(payload)
                image_id = image_id or _image_id(payload.get('image_id') or payload.get('image'))
                admission = payload.get('admission') or payload.get('admissions', {}).get('candidate') or {}
                image_id = image_id or _image_id(admission.get('image'))
                effective = effective or payload.get('effective_config_line') or payload.get('effective')
                details = payload.get('details') or payload.get('run', {}).get('details', {})
                if isinstance(details, dict):
                    engagement = engagement or details.get('engagement_checks') or details.get('engagement')
                    effective = effective or details.get('effective_config_line') or details.get('effective')
                engagement = engagement or payload.get('engagement') or payload.get('engagement_checks')
                candidate_ab = payload.get('ab_result') or (payload if r.get('kind') == 'ab_result' else None)
                if candidate_ab:
                    ab = {k: candidate_ab.get(k) for k in ('gate', 'ratio', 'aa_gap', 'output_class', 'acceptance', 'per_arm_ms')}
        refs += [r.get('obs_id') or r.get('eval_id') or r.get('attempt_id') or r.get('decision_id') for r in linked]
        refs += [aid for r in linked for aid in r.get('source_artifacts', [])]
        result.append(dict(component=component, action=action.get('type', root.get('kind')),
            applied=True if action.get('type') == 'keep_component' or root.get('kind') == 'component_applied' else action.get('applied'),
            source_commit=commit, files_changed=files, image_id=image_id, effective_config=effective,
            reason=str(root.get('reason_for_change') or root.get('hypothesis') or action.get('reason') or '')[:600] or None,
            evidence_ids=list(dict.fromkeys(r for r in refs if r)), engagement=engagement, ab_result=ab,
            source=root.get('decision_id') or root.get('obs_id'),
            coverage='explicit evidence/attempt links only; unlinked fields UNKNOWN'))
    return result


@contextmanager
def _snapshot_store(home):
    """Store's constructor mutates: run it only on a stable private DB/WAL copy."""
    from ..store import Store

    home = Path(home).expanduser().resolve()
    dbfiles = [home / 'factory.sqlite', home / 'factory.sqlite-wal']
    if not dbfiles[0].is_file():
        raise ValueError('Factory database does not exist; no home was created')
    def stamps():
        return [(p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else None for p in dbfiles]
    with tempfile.TemporaryDirectory(prefix='factory-activity-') as temporary:
        target = Path(temporary)
        for _ in range(5):
            before = stamps()
            for path in dbfiles:
                destination = target / path.name
                if path.is_file():
                    shutil.copyfile(path, destination)
                else:
                    destination.unlink(missing_ok=True)
            if before == stamps():
                break
        else:
            raise ValueError('Factory evidence changed during copy; retry')
        # Only artifact reads use this link. Store mutations stay in the copy.
        (target / 'artifacts').symlink_to(home / 'artifacts', target_is_directory=True)
        with Store(target) as store:
            yield store


def _read_records(store, task_id):
    task = store.get_task(task_id)
    records = dict(tasks=[task], decisions=[], observations=[], attempts=[], evaluations=[])
    mapping = dict(decision='decisions', observation='observations', attempt='attempts', evaluation='evaluations')
    cursor, seen, artifacts = 0, set(), []
    while True:
        page = store.query(task_id, since=cursor, limit=50)
        for item in page['items']:
            if item['type'] == 'artifact':
                if item['id'] not in artifacts:
                    artifacts.append(item['id'])
                continue
            identity = (item['type'], item['id'])
            if item['type'] in mapping and identity not in seen:
                seen.add(identity)
                records[mapping[item['type']]].append(store.read(task_id, item['id']))
        if not page['items']:
            break
        cursor = page['cursor']
    return records, artifacts


def _task_activity(store, task_id, home, trace_run, mode):
    records, artifact_ids = _read_records(store, task_id)
    runs = sorted((r for r in records['observations'] if r.get('kind') in ('lab_result', 'ab_result')),
                  key=lambda r: r.get('created', 0))
    chosen = next((r for r in reversed(runs) if any(a.endswith('stderr.txt') for a in r.get('source_artifacts', []))), {})
    refs = chosen.get('source_artifacts', [])
    stderr_ids = [a for a in refs if a.endswith('stderr.txt')]
    candidate_ids = [a for a in stderr_ids if '-candidate/' in a]
    stderr_id = (candidate_ids or stderr_ids or [None])[-1]
    # An A/B task contains multiple arms. Pick one recorded arm and say which;
    # never concatenate stderr from incomparable images/configurations.
    prefix = stderr_id[:-len('stderr.txt')] if stderr_id else None
    sources, content = [], {}
    if prefix is not None:
        for name in ('stderr.txt', 'result.json', 'summary.json', 'threads.summary.json', *TRACE_NAMES):
            aid = prefix + name
            if aid not in artifact_ids:
                continue
            raw = store.artifact_bytes(task_id, aid)
            content[name] = raw
            kind = ('expert-trace' if name in TRACE_NAMES else 'engine-stats' if name == 'stderr.txt' else
                    'run-result' if name == 'result.json' else 'thread-summary' if name == 'threads.summary.json' else 'run-summary')
            sources.append(_source(f'{home}#{task_id}/{aid}', raw, kind,
                f'factory artifact {aid}; selected recorded arm only',
                _overhead('trace: operator A/B required; unmeasured') if name in TRACE_NAMES else
                _overhead('external thread sampler; self CPU is not engine overhead A/B') if name == 'threads.summary.json' else
                _overhead('offline metadata; collection cost UNKNOWN') if name != 'stderr.txt' else None))
    def json_content(name):
        return json.loads(content.get(name, b'{}'))
    source = next((s['path'] for s in sources if s['kind'] == 'engine-stats'), 'factory stderr UNKNOWN')
    stats = parse_stderr(content.get('stderr.txt', b'').decode(errors='replace'), source)
    for s in sources:
        if s['kind'] == 'engine-stats':
            s['overhead'] = _stats_overhead(stats)
    trace = None
    trace_names = [name for name in TRACE_NAMES if name in content]
    config_trace = (stats.get('effective_config') or {}).get('trace')
    config_name = Path(config_trace).name if isinstance(config_trace, str) and config_trace != '(unset)' else None
    if prefix is not None and config_name and prefix + config_name in artifact_ids and config_name not in trace_names:
        raw = store.artifact_bytes(task_id, prefix + config_name)
        content[config_name] = raw
        trace_names.append(config_name)
        sources.append(_source(f'{home}#{task_id}/{prefix}{config_name}', raw, 'expert-trace',
                               'trace named in effective config; selected recorded arm only',
                               _overhead('trace: operator A/B required; unmeasured')))
    if len(trace_names) == 1:
        name = trace_names[0]
        trace = parse_trace(content[name].decode(errors='replace'), f'{home}#{task_id}/{prefix}{name}', run_id=prefix or task_id, trace_run=trace_run)
        if len(trace['metadata']) == 1:
            declared = next(iter(trace['metadata'].values())).get('overhead')
            for s in sources:
                if s['kind'] == 'expert-trace':
                    s['overhead'] = _overhead('trace: operator A/B required; unmeasured', declared)
    changes = build_changes(records)
    for change in changes:
        if chosen.get('obs_id') in change['evidence_ids'] and change['effective_config'] is None:
            change['effective_config'] = stats.get('effective_config_line')
    metadata = dict(notes=[f'Factory Store API snapshot. Selected observation {chosen.get("obs_id", "UNKNOWN")}; arm {prefix or "UNKNOWN"}. Other arms are not pooled.'])
    if len(trace_names) > 1:
        metadata['notes'].append('Multiple trace artifacts for selected arm; trace selection UNKNOWN. Export an arm directory and use --trace to choose one.')
    sources.append(dict(path=f'{home}/factory.sqlite#{task_id}', kind='factory-store', sha256=None,
                        coverage='all task record pages via Store.query/read; artifact bytes verified by Store',
                        overhead=_overhead('offline evidence read; outside engine timing window')))
    return build_activity(stats, trace, metadata=metadata, sources=sources,
        result=json_content('result.json'), summary=json_content('summary.json'),
        threads=json_content('threads.summary.json') or None, run_id=prefix or task_id, task_id=task_id,
        changes=changes, mode=mode)


def load_task(task_id, *, home=None, trace_run=None, mode='replay', store=None):
    """Use an existing Store API, or copy a home before opening it. Never create it."""
    if store is not None:
        return _task_activity(store, task_id, str(home or 'Store API'), trace_run, mode)
    home = Path(home or os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory')).expanduser().resolve()
    with _snapshot_store(home) as snapshot:
        return _task_activity(snapshot, task_id, str(home), trace_run, mode)


def load_activity(source, *, home=None, trace_path=None, trace_run=None, mode='replay'):
    path = Path(source).expanduser()
    if path.is_dir():
        return load_run(path, trace_path=trace_path, trace_run=trace_run, mode=mode)
    if trace_path is not None:
        raise ValueError('--trace requires a run directory')
    return load_task(str(source), home=home, trace_run=trace_run, mode=mode)
