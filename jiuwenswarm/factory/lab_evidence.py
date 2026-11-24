"""Bounded parent-scoped inspection of collected benchmark child evidence.

This importer never reconciles a job, executes a model, or widens evidence scope.
Raw allowlisted files become immutable, host-owned parent artifacts.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
from .store import NotFound, ScopeDenied, encoded

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
ALLOWED_RAW = {'stdout.log', 'stderr.log', 'samples.jsonl', 'report.json', 'pipe-events.jsonl'}
ADAPTERS = {'strata-benchmark-v1', 'strata-benchmark-v2', 'strata-benchmark-v3', 'strata-benchmark-v4', 'strata-benchmark-v5'}

def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def read_json(path):
    return json.loads(path.read_text())


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_manifest(root, *, allow_partial=False):
    manifest = read_json(root / 'manifest.json')
    if manifest.get('state') not in ({'complete', 'partial'} if allow_partial else {'complete'}):
        raise ValueError('Only completed evidence manifests may be analyzed')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
              if p.is_file() and p != root / 'manifest.json'
              and not p.name.endswith('.lock') and not p.name.startswith('.')}
    expected = manifest.get('files')
    if not isinstance(expected, dict) or set(expected) != actual:
        raise ValueError('Manifest coverage differs from retained files')
    sizes = [(root / name).stat().st_size for name in expected]
    if len(sizes) > 1024 or sum(sizes) > MAX_TOTAL_BYTES or any(size > MAX_FILE_BYTES for size in sizes):
        raise ValueError('Manifest exceeds bounded inspection size')
    for name, digest in expected.items():
        candidate = root / name
        path = candidate.resolve(strict=True)
        if candidate.is_symlink() or not path.is_relative_to(root.resolve()):
            raise ValueError('Evidence path escapes its spool or is a symlink')
        with path.open('rb') as stream:
            observed = hashlib.file_digest(stream, 'sha256').hexdigest()
        if observed != digest:
            raise ValueError('Evidence SHA256 mismatch: ' + name)
    return manifest


def event_time(events, stream, end_offset):
    for event in events:
        if (event.get('stream') == stream and number(event.get('offset'))
                and number(event.get('retained_bytes'))
                and event['offset'] < end_offset <= event['offset'] + event['retained_bytes']):
            stamp = event.get('monotonic_ns')
            return stamp if number(stamp) else None
    return None


def elapsed(start, end):
    return (end - start) / 1e9 if number(start) and number(end) and end >= start else None


def counter_interval(samples, field, key):
    points = [(s.get('monotonic_ns'), s.get(field, {}).get(key)) for s in samples
              if isinstance(s.get(field), dict) and number(s.get(field, {}).get(key))
              and number(s.get('monotonic_ns'))]
    if len(points) < 2:
        return dict(delta=None, interval_s=None, status='unknown_insufficient_counter_samples')
    if any(b[1] < a[1] for a, b in zip(points, points[1:])):
        return dict(delta=None, interval_s=None, status='unknown_counter_reset')
    duration = elapsed(points[0][0], points[-1][0])
    if not duration:
        return dict(delta=None, interval_s=duration, status='unknown_nonpositive_interval')
    return dict(delta=points[-1][1] - points[0][1], interval_s=duration,
                first=points[0][1], last=points[-1][1], status='observed_endpoint_difference')


def parse_io(value):
    devices = {}
    if not isinstance(value, str):
        return None
    for line in value.splitlines():
        parts = line.split()
        if not parts:
            continue
        fields = dict(item.split('=', 1) for item in parts[1:] if '=' in item)
        if 'rbytes' not in fields or not fields['rbytes'].isdigit():
            return None
        devices[parts[0]] = int(fields['rbytes'])
    return devices


def io_interval(samples):
    points = [(s.get('monotonic_ns'), parse_io(s.get('io_stat'))) for s in samples]
    points = [(stamp, devices) for stamp, devices in points if number(stamp) and devices is not None]
    if len(points) < 2:
        return dict(read_bytes=None, status='unknown_insufficient_io_samples')
    keys = set(points[0][1])
    if any(set(devices) != keys for _, devices in points):
        return dict(read_bytes=None, status='unknown_device_set_changed')
    if any(any(b[1][key] < a[1][key] for key in keys) for a, b in zip(points, points[1:])):
        return dict(read_bytes=None, status='unknown_counter_reset')
    return dict(read_bytes=sum(points[-1][1].values()) - sum(points[0][1].values()),
                interval_s=elapsed(points[0][0], points[-1][0]), devices=sorted(keys),
                status='observed_endpoint_difference')


def phase_summary(path):
    events = read_jsonl(path / 'pipe-events.jsonl')
    samples = read_jsonl(path / 'samples.jsonl')
    report = read_json(path / 'report.json')
    if not (report.get('reason') == 'completed' and report.get('quiescent') is True
            and report.get('container_removed') is True and report.get('container_exit_code') == 0):
        raise ValueError('Phase did not complete and clean up')
    gate = next((e.get('monotonic_ns') for e in events if e.get('stream') == 'stdin'), None)
    ready = None
    infos, requests = [], []
    offset, first_token, token_count = 0, None, 0
    for line in (path / 'stdout.log').read_bytes().splitlines(keepends=True):
        offset += len(line)
        parts = line.decode('utf-8', errors='strict').split()
        if not parts:
            continue
        stamp = event_time(events, 'stdout', offset)
        if parts[0] == 'INFO':
            # Numeric engine state only; never copy raw model outputs.
            fields = dict(v.split('=', 1) for v in parts[1:] if '=' in v)
            selected = {k: int(fields[k]) for k in ('context', 'kv_resident', 'expert_slots', 'cpu_experts',
                        'ram_experts', 'engram_layers', 'engram_lookups') if fields.get(k, '').isdigit()}
            if selected:
                infos.append(selected)
        elif parts[0] == 'READY':
            ready = stamp
        elif parts[0] == 'T':
            if token_count == 0:
                first_token = stamp
            token_count += 1
            if token_count > 128:
                raise ValueError('Native request exceeds retained token bound')
        elif parts[0] == 'DONE':
            if len(requests) >= 128:
                raise ValueError('Native request count exceeds summary bound')
            if len(parts) != 11 or int(parts[1]) != token_count:
                raise ValueError('Invalid retained native DONE framing')
            prefill, decode = float(parts[3]), float(parts[4])
            if not number(prefill) or not number(decode) or not prefill or not decode:
                raise ValueError('Invalid native request timing')
            requests.append(dict(index=len(requests) + 1, generated_tokens=token_count,
                prompt_tokens=int(parts[2]), prefill_ms=prefill, decode_ms=decode,
                native_prefill_plus_decode_ms=prefill + decode, finish=parts[5],
                accepted_drafts=int(parts[6]), offered_drafts=int(parts[7]),
                observed_first_token_monotonic_ns=first_token,
                observed_first_token_since_gate_s=elapsed(gate, first_token),
                observed_first_token_since_ready_s=elapsed(ready, first_token),
                request_to_first_token_ms=None,
                first_token_scope='Collector pipe observation; request start not separately observed. Since-gate includes startup and prior requests.',
                decode_tokens_per_second=token_count * 1000 / decode))
            token_count, first_token = 0, None
    if token_count:
        raise ValueError('Unterminated native token sequence')
    stamps = [s['monotonic_ns'] for s in samples if number(s.get('monotonic_ns'))]
    host = [s['available_bytes'] for s in samples if number(s.get('available_bytes'))]
    memory = [s['cgroup_current'] for s in samples if number(s.get('cgroup_current'))]
    cpu = {key: counter_interval(samples, 'cpu_stat', key) for key in
           ('usage_usec', 'user_usec', 'system_usec', 'nr_periods', 'nr_throttled', 'throttled_usec')}
    usage = cpu['usage_usec']
    average_cores = usage['delta'] / (usage['interval_s'] * 1e6) if usage.get('delta') is not None and usage.get('interval_s') else None
    quota = report.get('cpus')
    return dict(cell=path.parent.name, phase=path.name, engine_info=infos or None,
        requests=requests, observed_ready_since_gate_s=elapsed(gate, ready),
        samples=dict(count=len(samples), observed_interval_s=elapsed(stamps[0], stamps[-1]) if stamps else None,
                     maximum_gap_s=max((b - a for a, b in zip(stamps, stamps[1:])), default=0) / 1e9 if len(stamps) > 1 else None),
        lifecycle_cpu=dict(counters=cpu, average_consumed_cores=average_cores, quota_cpus=quota,
            average_quota_utilization_pct=100 * average_cores / quota if average_cores is not None and number(quota) and quota else None),
        lifecycle_cgroup_io=io_interval(samples),
        lifecycle_process_read_bytes=counter_interval(samples, 'process_io', 'read_bytes'),
        memory=dict(host_available_min_bytes=min(host) if host else None,
                    sampled_cgroup_current_max_bytes=max(memory) if memory else None,
                    kernel_cgroup_peak_bytes=None,
                    peak_scope='Maximum observed memory.current sample; kernel memory.peak was not retained.'),
        gpu_utilization=None, gpu_utilization_status='not_measured_by_retained_recorder',
        cleanup=dict(container_removed=report.get('container_removed'), quiescent=report.get('quiescent'),
                     oom_killed=report.get('container_oom_killed')),
        resource_scope='Cgroup/process lifecycle sample interval includes initialization, prefill, decode and idle periods; no decode-phase causal allocation.')


def _archived_raw(host, parent, child, attempt, contract):
    """Expose verified collected artifact bytes when the source spool is gone."""
    order = contract.get('order')
    if not isinstance(order, list) or not 1 <= len(order) <= 16 or any(a not in {'A', 'B'} for a in order):
        raise ValueError('Archive cell count exceeds inspection bounds')
    pending, total = [], 0
    for index, arm in enumerate(order, 1):
        for phase in ('quality', 'speed'):
            for name in sorted(ALLOWED_RAW):
                source = f'cell-{index:03d}-{arm}/{phase}/{name}'
                try:
                    artifact = host.read_artifact(child, attempt + ':' + source)
                except NotFound:
                    continue
                total += artifact['size']
                if artifact['size'] > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                    raise ValueError('Archived raw evidence exceeds import bounds')
                data = host.artifact_bytes(child, artifact['artifact_id'])
                aid = 'lab-evidence:' + attempt + ':' + hashlib.sha256(source.encode()).hexdigest()[:24]
                try:
                    previous = host.read_artifact(parent, aid)
                except NotFound:
                    previous = None
                if previous and (previous['sha256'] != artifact['sha256'] or host.artifact_bytes(parent, aid) != data):
                    raise ValueError('Existing parent artifact differs from collected archive')
                pending.append((aid, source, data, artifact, previous))
    result = []
    for aid, source, data, original, previous in pending:
        installed = previous or host.put_artifact(parent, aid, data, original['media_type'], attempt)
        result.append(dict(artifact_id=installed['artifact_id'], source_path=source,
            sha256=original['sha256'], size=original['size'], source_task_id=child,
            source_attempt_id=attempt, verification='collected_child_artifact_sha256_only'))
    return result


def inspect_evidence(store, task_id, cycle_id):
    if hasattr(store, '_check'):
        store._check(task_id, write=True)
    host = getattr(store, '_store', store)
    task = store.get_task(task_id)
    if not isinstance(cycle_id, str) or not cycle_id or len(cycle_id) > 100:
        raise ValueError('Bounded nonempty cycle_id required')
    exists = host._db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='factory_loop_cycles'").fetchone()
    row = host._db.execute('SELECT record FROM factory_loop_cycles WHERE task_id=? AND cycle_id=?',
                          (task_id, cycle_id)).fetchone() if exists else None
    if row is None:
        raise ScopeDenied('Cycle is outside the current parent ledger')
    cycle = json.loads(row['record'])
    if cycle.get('state') != 'collected':
        raise ValueError('Collect the completed benchmark cycle before inspecting evidence')
    child_id, attempt_id = cycle['child_task_id'], cycle['attempt_id']
    child = host.get_task(child_id)
    attempt_row = host._db.execute('SELECT * FROM attempts WHERE task_id=? AND attempt_id=?',
                                  (child_id, attempt_id)).fetchone()
    if not attempt_row:
        raise ScopeDenied('Ledger attempt does not belong to its child task')
    attempt = host._decode('attempts', attempt_row)
    contract = cycle['contract']
    request = attempt['request']
    if (child.get('constraints', {}).get('factory_loop_parent') != task_id
            or attempt['kind'] != 'lab' or attempt['state'] not in {'succeeded', 'failed', 'cancelled'}
            or contract.get('adapter') not in ADAPTERS or request.get('adapter') != contract['adapter']
            or request.get('contract') != contract or request.get('contract_sha256') != cycle.get('contract_sha256')):
        raise ScopeDenied('Collected benchmark ownership or frozen contract differs')
    policy = task.get('constraints', {}).get('factory_loop', {})
    template = next((t for t in policy.get('templates', []) if t.get('id') == cycle['request']['template_id']), None)
    if not template or template.get('sha256') != cycle.get('template_sha256'):
        raise ScopeDenied('Cycle template is outside parent admission')
    template_bytes = Path(template['path']).read_bytes()
    if hashlib.sha256(template_bytes).hexdigest() != template['sha256'] or json.loads(template_bytes) != contract:
        raise ValueError('Admitted template bytes or contract changed')
    contract_bytes = Path(request['contract_path']).read_bytes()
    if (hashlib.sha256(contract_bytes).hexdigest() != cycle['contract_sha256']
            or json.loads(contract_bytes) != contract or child.get('contract_id') != request['contract_path']):
        raise ValueError('Child contract identity changed')
    if os.environ.get('FACTORY_BRIDGE_DIR'):
        from .bridge import call
        result = call('lab_evidence_inspect', task_id=task_id, cycle_id=cycle_id)
        result.check_returncode()
        return json.loads(result.stdout)
    spool_base = (host.home / 'benchmark-spool').resolve()
    spool = (spool_base / attempt_id).resolve()
    if not spool.is_relative_to(spool_base):
        raise ScopeDenied('Attempt spool escaped its host root')
    manifest_path = spool / 'manifest.json'
    if not manifest_path.is_file():
        archived = _archived_raw(host, task_id, child_id, attempt_id, contract)
        return dict(schema='factory.lab-evidence/1', cycle_id=cycle_id, parent_task_id=task_id,
            child_task_id=child_id, attempt_id=attempt_id, execution_complete=False, diagnostic_only=True,
            evidence_status='retained_archive_only' if archived else 'unavailable_unsealed_raw',
            raw_source_verified=False, artifacts=archived, phases=[],
            limitation='No sealed raw manifest exists; only existing collected child artifacts with independently verified stored SHA256 may be exposed. Arbitrary spool files are never imported or scored.')
    raw_manifest = manifest_path.read_bytes()
    # Collected Benchmark.result imported this immutable original. Do not accept
    # a rewritten spool manifest even when an attacker updates its file hashes.
    original_manifest = host.artifact_bytes(child_id, attempt_id + ':manifest.json')
    if raw_manifest != original_manifest:
        raise ValueError('Raw manifest differs from the collected child artifact')
    manifest = verify_manifest(spool, allow_partial=attempt['state'] != 'succeeded')
    complete = attempt['state'] == 'succeeded' and manifest['state'] == 'complete'
    config = read_json(spool / 'config.json') if (spool / 'config.json').is_file() else None
    campaign = read_json(spool / 'campaign.json')
    if (manifest.get('task_id') != child_id or manifest.get('attempt_id') != attempt_id
            or (config is not None and (config.get('task_id') != child_id or config.get('attempt_id') != attempt_id
                or config.get('contract') != contract)) or (complete and config is None)
            or campaign.get('task_id') != child_id
            or campaign.get('attempt_id') != attempt_id or campaign.get('contract_sha256') != cycle['contract_sha256']
            or (complete and (campaign.get('execution_outcome') != 'ok' or campaign.get('evidence_completeness') != 'complete'))):
        raise ValueError('Raw campaign identity, contract or completeness differs')
    if (not isinstance(contract.get('order'), list) or not 1 <= len(contract['order']) <= 16
            or any(arm not in {'A', 'B'} for arm in contract['order'])):
        raise ValueError('Evidence cell count exceeds inspection bound')
    phases = [spool / f'cell-{i:03d}-{arm}' / phase
              for i, arm in enumerate(contract['order'], 1) for phase in ('quality', 'speed')]
    selected = [(path / name) for path in phases for name in sorted(ALLOWED_RAW)
                if (path / name).is_file()]
    if complete and len(selected) != len(phases) * len(ALLOWED_RAW):
        raise ValueError('Complete campaign lacks required phase evidence files')
    total = sum(path.stat().st_size for path in selected)
    if total > MAX_TOTAL_BYTES or any(path.stat().st_size > MAX_FILE_BYTES for path in selected):
        raise ValueError('Raw evidence exceeds bounded parent import size')
    summaries = []
    for path in phases:
        if not path.is_dir() and not complete:
            continue
        try:
            summaries.append(phase_summary(path))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if complete:
                raise
            summaries.append(dict(cell=path.parent.name, phase=path.name, evidence_status='partial_raw_only',
                execution_complete=False, diagnostic_only=True, error=type(exc).__name__,
                native_rates=None, resource_summary=None,
                limitation='Incomplete phase; inspect verified raw artifacts. No scoring or complete execution claim.'))
    copied = []
    # Check all existing copies before writing anything new.
    payloads = []
    for path in selected:
        name = path.relative_to(spool).as_posix()
        if name not in manifest['files']:
            raise ValueError('Raw file is outside verified manifest')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != manifest['files'][name]:
            raise ValueError('Raw file changed during evidence inspection')
        aid = 'lab-evidence:' + attempt_id + ':' + hashlib.sha256(name.encode()).hexdigest()[:24]
        try:
            existing = host.read_artifact(task_id, aid)
        except NotFound:
            existing = None
        if existing is not None and (existing['sha256'] != digest or host.artifact_bytes(task_id, aid) != data):
            raise ValueError('Existing parent artifact differs from immutable child evidence')
        payloads.append((aid, name, data, digest, existing))
    for aid, name, data, digest, existing in payloads:
        artifact = existing or host.put_artifact(task_id, aid, data,
                    'application/json' if name.endswith('.json') else 'application/x-ndjson' if name.endswith('.jsonl') else 'text/plain', attempt_id)
        copied.append(dict(artifact_id=artifact['artifact_id'], source_path=name, sha256=digest, size=len(data),
                           source_task_id=child_id, source_attempt_id=attempt_id))
    report = dict(schema='factory.lab-evidence/1', cycle_id=cycle_id, parent_task_id=task_id,
        child_task_id=child_id, attempt_id=attempt_id, contract_sha256=cycle['contract_sha256'],
        manifest_sha256=hashlib.sha256(raw_manifest).hexdigest(), verified_manifest_files=len(manifest['files']),
        execution_complete=complete, diagnostic_only=not complete,
        evidence_status='complete_verified' if complete else 'partial_manifest_verified',
        phases=summaries, artifacts=copied, descriptive_only=True, execution_authorized=False,
        promotion_authorized=False,
        limitations=['Resource samples span process startup, prefill, decode and idle; they are not decode-causal attribution.',
            'First-token pipe observations include buffering and prior work; true per-request TTFT is unknown.',
            'Sampled memory.current maxima are lower bounds; kernel memory.peak and GPU utilization were not retained.',
            'This inspection checks retained evidence integrity/ownership; it does not rescore quality or speed.'])
    obs_id = 'lab-evidence:' + attempt_id + ':inspection'
    try:
        previous = host.read(task_id, obs_id)
    except NotFound:
        previous = None
    if previous and previous.get('values') != report:
        raise ValueError('Existing historical inspection differs; refusing to overwrite it')
    if previous is None:
        host.append_observation(task_id, dict(obs_id=obs_id, kind='lab_evidence_inspection', values=report,
            source_artifacts=[a['artifact_id'] for a in copied],
            host_run=dict(child_task_id=child_id, attempt_id=attempt_id),
            limitations='Host verified parent-scoped import, not an execution or promotion grant.'))
    return dict(report, observation_id=obs_id)


def dispatch(store, task_id, operation, inputs):
    if operation != 'inspect' or not isinstance(inputs, dict) or set(inputs) != {'cycle_id'}:
        raise ValueError('Evidence inspection requires only cycle_id')
    return {'result': inspect_evidence(store, task_id, inputs['cycle_id'])}
