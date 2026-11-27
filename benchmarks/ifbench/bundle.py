"""Portable, offline-verifiable Lab Agent handoff. Never includes model weights."""
import hashlib
import json
import shutil
import tarfile
from pathlib import Path
from .telemetry import CATALOG
from .requests import summary


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def verify(folder):
    root = Path(folder).resolve()
    errors = []
    hashes = json.loads((root / 'checksums.json').read_text())
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} - {'checksums.json'}
    if actual != set(hashes):
        errors.append('file set differs from checksum manifest')
    for name, expected in hashes.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or digest(path) != expected:
            errors.append('missing/unsafe/hash mismatch: ' + name)
    handoff = json.loads((root / 'handoff.json').read_text())
    if handoff.get('schema_version') != 1 or not handoff.get('runs'):
        errors.append('invalid handoff schema')
    for run in handoff['runs']:
        run_dir = root / 'runs' / run['run_id']
        for required in ('manifest.json', 'report.json', 'telemetry.jsonl', 'config.toml'):
            if not (run_dir / required).is_file():
                errors.append(run['run_id'] + ': missing ' + required)
        request_path = run_dir / 'requests.jsonl'
        if request_path.exists():
            for line in request_path.read_text(encoding='utf-8').splitlines():
                record = json.loads(line)
                count, elapsed, value = record['output_tokens'], record['elapsed_s'], record['e2e_output_tok_s']
                if count is None:
                    if value is not None or record['token_count_source'] != 'unavailable':
                        errors.append('unknown token count used for throughput')
                elif value is not None and abs(value - count / elapsed) > 1e-7:
                    errors.append('E2E throughput disagrees with raw count/time')
        if run.get('profiler_attached') and run.get('comparable'):
            errors.append('profile run incorrectly comparable')
        if run.get('profiler_attached') and run.get('status') == 'completed' and not all((run_dir / 'nsys' / name).is_file()
                                                  for name in ('profile.nsys-rep', 'profile.sqlite')):
            errors.append('missing original Nsight trace or SQLite')
        profile_summary = run_dir / 'nsys/profile_summary.json'
        if run.get('profiler_attached') and run.get('status') == 'completed' and not profile_summary.exists():
            errors.append('completed profile has no analysis summary')
        if run.get('profiler_attached') and run.get('status') == 'completed' and profile_summary.exists():
            profile = json.loads(profile_summary.read_text())
            if 'WARNING' in profile.get('clock', '') or not profile.get('windows'):
                errors.append('profile has no valid aligned GPU windows')
    return {'ok': not errors, 'files_checked': len(hashes), 'errors': errors}


def pack(runs, out, evidence=None, scope='small-model toolchain rehearsal; not Muse NVFP4 baseline'):
    root = Path(out).resolve()
    root.mkdir(parents=True, exist_ok=False)
    rows, coverage = [], {tid: [] for tid in CATALOG}
    for folder in runs:
        folder = Path(folder).resolve()
        manifest = json.loads((folder / 'manifest.json').read_text())
        report = json.loads((folder / 'report.json').read_text())
        rid = manifest['run_id']
        if Path(rid).name != rid:
            raise ValueError('Unsafe run ID')
        dest = root / 'runs' / rid
        shutil.copytree(folder, dest)
        rows.append({'run_id': rid, 'set': manifest.get('set'), 'status': report['status'], 'comparable': report['comparable'],
                     'profiler_attached': bool(manifest.get('profiler')), 'benchmarks': report['benchmarks'],
                     'request_summary': summary(dest / 'requests.jsonl')})
        for line in (dest / 'telemetry.jsonl').read_text().splitlines():
            record = json.loads(line)
            record.update(evidence=f'runs/{rid}/telemetry.jsonl')
            source = record.get('source', '').lower()
            record['measurement_kind'] = 'estimated' if 'estimate' in source else (
                'measured' if record['status'] == 'ok' else record['status'])
            coverage.setdefault(record['id'], []).append(record)
    if evidence:
        shutil.copytree(evidence, root / 'preflight')
        for path in sorted((Path(evidence) / 'diagnostics').glob('*/telemetry.jsonl')):
            for line in path.read_text().splitlines():
                record = json.loads(line)
                source = record.get('source', '').lower()
                record.update(evidence='preflight/' + path.relative_to(evidence).as_posix(),
                              measurement_kind='simulation' if 'replay' in source else 'diagnostic')
                coverage.setdefault(record['id'], []).append(record)
        reuse = Path(evidence) / 'reused-hardware-calibration'
        if (reuse / 'reuse.json').exists():
            provenance = json.loads((reuse / 'reuse.json').read_text())
            for line in (reuse / 'telemetry.jsonl').read_text().splitlines():
                record = json.loads(line)
                if record['id'] not in ('L6.cal.memory_bandwidth', 'L6.cal.compute'):
                    continue
                record.update(measurement_kind='reused_hardware_calibration', reuse=provenance,
                              evidence='preflight/reused-hardware-calibration/telemetry.jsonl')
                coverage[record['id']].append(record)
    source = Path(__file__).parent
    shutil.copytree(source, root / 'source/ifbench', ignore=shutil.ignore_patterns('__pycache__', 'data', 'examples'))
    for name in ('tests', 'tools'):
        src_dir = source.parent / name
        if src_dir.is_dir():
            (root / 'source' / name).mkdir()
            for path in src_dir.glob('*.py'):
                shutil.copy2(path, root / 'source' / name / path.name)
    data_dir = (source / 'data') if (source / 'data').is_dir() else (source.parent / 'data')
    (root / 'source/data').mkdir(parents=True)
    if data_dir.is_dir():
        for path in data_dir.glob('*'):
            if path.is_file():
                shutil.copy2(path, root / 'source/data' / path.name)
    for tid in coverage:
        coverage[tid] = sorted(coverage[tid], key=lambda r: {'ok': 0, 'not_applicable': 1}.get(r['status'], 2))
    merged = {tid: (records[0] if records else {'id': tid, 'value': None, 'status': 'unavailable',
                                              'note': 'not recorded'}) for tid, records in coverage.items()}
    trial = json.loads((root / 'preflight/trial.json').read_text()) if (root / 'preflight/trial.json').exists() else {}
    collection = json.loads((root / 'preflight/collection-state.json').read_text()) if (root / 'preflight/collection-state.json').exists() else {}
    ready = bool(rows) and all((r['status'] == 'completed' or (r['set'] == 'probe' and r['status'] == 'probe only'))
                              and all(b['outcome'] == 'ok' for b in r['benchmarks']) for r in rows)
    ready &= set(trial.get('required_sets', ())).issubset({r['set'] for r in rows if r['status'] == 'completed'})
    ready &= not bool(collection.get('failures'))
    handoff = {'schema_version': 1, 'trial_id': root.name,
               'status': 'completed' if ready else 'incomplete',
               'scope': scope,
               'verdict': None, 'verdict_reason': 'no candidate or frozen optimization thresholds',
               'runs': rows, 'required_returns': ['benchmarks', 'request_metrics', 'telemetry_coverage', 'profiles', 'integrity'],
               'artifacts': {'coverage': 'coverage.json', 'source': 'source', 'checksums': 'checksums.json'},
               'source_provenance': 'source contains packaging-time toolkit; preflight/runtime or preflight/runtime-timed preserves collection-time source when present',
               'integration': 'portable producer contract; live Lab Agent consumer not connected'}
    (root / 'handoff.json').write_text(json.dumps(handoff, indent=2))
    (root / 'coverage.json').write_text(json.dumps(merged, indent=2))
    extras = {'E2E_output_throughput': 'runs/*/requests.jsonl:e2e_output_tok_s',
              'decode_client_estimate': 'runs/*/requests.jsonl:decode_tok_s_client_estimate',
              'service_observed_throughput': 'handoff.json:runs[].request_summary.service_output_tok_s',
              'finish_reason_and_usage': 'runs/*/requests.jsonl',
              'worker_pss_and_interference': 'runs/*/samples.jsonl',
              'counter_permissions': 'preflight', 'integrity': 'checksums.json'}
    (root / 'additional-metrics.json').write_text(json.dumps(extras, indent=2))
    hashes = {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob('*')) if p.is_file()}
    (root / 'checksums.json').write_text(json.dumps(hashes, indent=2))
    result = verify(root)
    if not result['ok']:
        raise ValueError(result)
    archive = root.with_suffix('.tar.gz')
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(root, arcname=root.name)
    archive.with_suffix(archive.suffix + '.sha256').write_text(digest(archive) + '  ' + archive.name + '\n')
    return {'bundle': str(root), 'archive': str(archive), **result}
