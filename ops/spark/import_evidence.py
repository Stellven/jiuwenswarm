#!/usr/bin/env python3
"""Import retained Spark operator evidence into a native factory store; never run jobs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import mimetypes
from pathlib import Path
import time

from jiuwenswarm.factory.export import export_task, verify
from jiuwenswarm.factory.redact import sensitive
from jiuwenswarm.factory.store import NotFound, Store

STARS = ('observability_event_recorder', 'weight_placement_planner', 'expert_weight_cache',
         'expert_demand_predictor', 'batch_layout_mapper')
SUFFIXES = {'.json', '.jsonl', '.log', '.txt', '.sse', '.md', '.yaml', '.yml', '.mmd', '.csv', '.diff', '.patch', '.jinja'}
DENIED = {'auth.json', 'credentials.json', 'config.lock', '.env', '.codex', '.ssh', 'id_rsa', 'id_ed25519'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_bytes(path):
    path = Path(path)
    if any(parent.is_symlink() for parent in (path, *path.parents)) or any(part.lower() in DENIED for part in path.parts):
        raise ValueError('Credential or symlink input is not allowed: ' + path.name)
    if not path.is_file():
        raise ValueError('Evidence input must be a regular file: ' + path.name)
    data = path.read_bytes()
    try:
        value = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        value = None
    def check(item):
        if isinstance(item, dict):
            for key, val in item.items():
                if sensitive(str(key), val):
                    raise ValueError('Credential field in evidence input: ' + path.name)
                check(val)
        elif isinstance(item, list):
            for child in item:
                check(child)
    check(value)
    return data


def collect(base, repo, attachments):
    groups = [(base / 'OPS/runs', 'OPS/runs'), (repo / 'ops/spark/prompts', 'prompts'),
              (base / 'inputs/ontology', 'ontology')]
    for root, prefix in groups:
        if root.is_dir():
            for path in sorted(root.rglob('*')):
                if path.is_file() and (path.suffix in SUFFIXES or path.name == 'SHA256SUMS'):
                    yield path, prefix + '/' + path.relative_to(root).as_posix()
    for name in ('STATUS.md', 'DECISIONS.md', 'BLOCKERS.md', 'LEDGER.jsonl'):
        path = base / 'OPS' / name
        if path.is_file():
            yield path, 'OPS/' + name
    for path in sorted((repo / 'jiuwenswarm/factory/contracts').glob('star-deepseek-v1.*')):
        yield path, 'contracts/' + path.name
    for star in STARS:
        for name in ('cc.yaml', 'ONTOLOGY.yaml', 'SHA256SUMS', 'METHOD.md', 'ACCEPTANCE.md', 'SOURCE-MAP.md'):
            path = repo / 'jiuwenswarm/factory/ccs' / star / name
            if path.is_file():
                yield path, 'capsules/' + star + '/' + name
    for path in attachments:
        path = Path(path).expanduser()
        yield path, 'attached/' + path.name


def memory_summary(run, captured=None):
    captured = captured or {}
    def content(path):
        return captured.get(path.resolve(), b'') if captured else safe_bytes(path)
    completed = run / 'result.json'
    if completed.is_file():
        result = json.loads(content(completed))
        if 'peak_memory_bytes' in result:
            return {key: result.get(key) for key in ('peak_memory_bytes', 'peak_rss_bytes', 'memory_events', 'min_mem_available_bytes')} | {'memory_basis': 'completed server scope peak; not request-specific'}
    peak = 0
    available = None
    path = run / 'memory.jsonl'
    if path.is_file():
        for line in content(path).splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue  # A concurrently written final line may be incomplete.
            peak = max(peak, row.get('peak', 0))
            current = row.get('available')
            available = min(available, current) if available is not None and current is not None else current
    return {'peak_memory_bytes': peak or None, 'min_mem_available_bytes': available,
            'memory_basis': 'sampled server scope lifetime peak at import; not request-specific'}


def measurement(result, request, server, load, memory, prompt_manifest):
    target = result.get('prompt_tokens')
    actual = result.get('usage', {}).get('prompt_tokens')
    if actual is None:
        actual = result.get('timings', {}).get('prompt_n')
    pinned = next((p for p in prompt_manifest.get('prompts', [])
                   if p.get('target_tokens_including_template') == target), {})
    reasons = []
    discarded = bool(result.get('discard', result.get('discarded', False)))
    if discarded:
        reasons.append('discarded first/cold request')
    if not result.get('ok') or not isinstance(result.get('ttft_s'), (int, float)) or result.get('ttft_s', 0) <= 0:
        reasons.append('request failed or incomplete')
    if result.get('timings', {}).get('cache_n', 0):
        reasons.append('prompt cache reuse')
    if target not in (512, 2048) or actual != target:
        reasons.append('actual prompt tokens do not match approved target')
    if not pinned or result.get('prompt_sha256') != pinned.get('prompt_sha256'):
        reasons.append('prompt SHA does not match fixed approved prompt manifest')
    if request.get('temperature') != 0 or request.get('max_tokens') != 32:
        reasons.append('request does not match temperature 0 / 32-token contract')
    return dict(result, prompt_tokens=actual, requested_prompt_tokens=target,
                discarded=discarded, warm=not discarded,
                measurement_eligible=not reasons, exclusion_reasons=reasons,
                command=server.get('command'), command_sha256=digest(json.dumps(server.get('command'), sort_keys=True).encode()),
                binary_sha256=server.get('binary_sha256'),
                load_time_s=load.get('load_time_s_from_engine_log', load.get('engine_reported_load_time_s', load.get('load_time_s'))),
                **memory)


def append_once(store, task_id, record):
    try:
        store.read(task_id, record['obs_id'])
        return False
    except NotFound:
        store.append_observation(task_id, record)
        return True


def import_evidence(base, repo, home, task_id='spark-direct-benchmarks-20261120', attachments=()):
    base, repo, home = map(lambda p: Path(p).expanduser().resolve(), (base, repo, home))
    home.mkdir(parents=True, exist_ok=True)
    with (home / 'evidence-import.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with Store(home) as store:
            try:
                store.get_task(task_id)
            except NotFound:
                store.create_task(dict(task_id=task_id,
                    objective='Lead engineer direct benchmark evidence import; no factory decision agent executed this task',
                    source={'mode': 'lead-direct-import', 'operator_evidence_root': str(base / 'OPS/runs')},
                    constraints={'no_model_launch': True, 'no_agent_session_claim': True},
                    budget={}, allowed_effects=[], contract_id='star-deepseek-v1'))
            imported = []
            by_path = {}
            captured = {}
            for path, label in collect(base, repo, attachments):
                data = safe_bytes(path)
                sha = digest(data)
                artifact_id = 'source:' + label + '@sha256:' + sha
                store.put_artifact(task_id, artifact_id, data,
                                   mimetypes.guess_type(path.name)[0] or 'text/plain', None)
                imported.append({'path': label, 'artifact_id': artifact_id, 'sha256': sha, 'size': len(data)})
                by_path[path.resolve()] = artifact_id
                captured[path.resolve()] = data
            manifest_data = json.dumps(imported, sort_keys=True).encode()
            snapshot_id = digest(manifest_data)
            count = 0
            manifest_path = repo / 'ops/spark/prompts/MANIFEST.json'
            prompts = json.loads(safe_bytes(manifest_path)) if manifest_path.is_file() else {}
            for path in sorted((base / 'OPS/runs').rglob('result.json')):
                if path.resolve() not in captured:
                    continue  # Result appeared after this import snapshot; next invocation retains it.
                raw = captured[path.resolve()]
                result = json.loads(raw)
                request_path = path.parent / 'request.json'
                start_path = next((parent / 'start.json' for parent in (path.parent, *path.parents)
                                   if (parent / 'start.json').is_file()), None)
                server = json.loads(safe_bytes(start_path)) if start_path else {}
                scope = start_path.parent if start_path else path.parent
                refs = [identifier for source, identifier in by_path.items()
                        if source.parent == path.parent or source in {scope / name for name in ('start.json', 'load-ready.json', 'memory.jsonl', 'stderr.log', 'stdout.log')}]
                refs.extend(identifier for source, identifier in by_path.items() if source.parent == manifest_path.parent or source.parent == repo / 'jiuwenswarm/factory/contracts')
                if request_path.is_file():
                    request = json.loads(captured[request_path.resolve()])
                    load_path = scope / 'load-ready.json'
                    load = json.loads(captured[load_path.resolve()]) if load_path.resolve() in captured else {}
                    values = measurement(result, request, server, load, memory_summary(scope, captured), prompts)
                    kind = 'measurement' if values['measurement_eligible'] else 'request_excluded'
                    values['prompt_manifest_sha256'] = digest(captured[manifest_path.resolve()]) if manifest_path.resolve() in captured else None
                    contract_path = repo / 'jiuwenswarm/factory/contracts/star-deepseek-v1.json'
                    values['contract_sha256'] = digest(captured[contract_path.resolve()]) if contract_path.resolve() in captured else None
                    values['message'] = f"{values.get('arm')} {values.get('prompt_tokens')} actual tokens: " + ('eligible warm request' if values['measurement_eligible'] else '; '.join(values['exclusion_reasons']))
                else:
                    kind = 'safety_test' if server.get('enforcement_test') else 'server_scope'
                    values = dict(result, message=f"{kind} {path.parent.name}: returncode={result.get('returncode')}; retained without benchmark attribution")
                count += append_once(store, task_id, dict(obs_id='import:result:' + digest(str(path.relative_to(base)).encode() + raw),
                    kind=kind, values=values, source_artifacts=refs,
                    limitations='Imported direct operator work, not factory-agent execution. Memory is a server scope peak.'))
            changed = append_once(store, task_id, dict(obs_id='import:snapshot:' + snapshot_id,
                kind='evidence_import', values={'message': f'Lead engineer imported {len(imported)} original evidence files; no model/agent launched',
                                               'mode': 'lead-direct-import', 'files': imported},
                source_artifacts=[item['artifact_id'] for item in imported]))
            if changed:
                session = home / 'sessions' / (task_id + '.jsonl')
                session.parent.mkdir(exist_ok=True)
                with session.open('a') as stream:
                    stream.write(json.dumps({'event': 'operator.evidence.import', 't': time.time(), 'actor': 'lead-direct-import',
                                             'snapshot_sha256': snapshot_id, 'files': len(imported), 'agent_executed': False}) + '\n')
            return {'task_id': task_id, 'home': str(home), 'artifacts': len(imported), 'new_observations': count + int(changed), 'snapshot_sha256': snapshot_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path.home() / 'predemo-spark')
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--home', type=Path)
    parser.add_argument('--task-id', default='spark-direct-benchmarks-20261120')
    parser.add_argument('--attach', type=Path, action='append', default=[])
    parser.add_argument('--export', type=Path, help='New export destination; existing paths are never overwritten')
    args = parser.parse_args()
    home = args.home or args.base / 'factory-runs/spark-direct-benchmarks'
    result = import_evidence(args.base, args.repo, home, args.task_id, args.attach)
    if args.export:
        result['export'] = str(export_task(args.task_id, args.export, home))
        result['verified_manifest_files'] = verify(args.export)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
