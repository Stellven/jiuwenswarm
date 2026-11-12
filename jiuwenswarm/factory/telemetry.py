"""Best-effort append-only factory telemetry. All writers share a locked sequence."""
from __future__ import annotations
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import time
from functools import lru_cache
from .redact import sanitize

SCHEMA = 'factory.telemetry/1'


def home_path(home=None):
    return Path(home or os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory')).expanduser().resolve()


def error(home, event, exc):
    try:
        directory = home_path(home) / 'telemetry'
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'errors.jsonl').open('a') as out:
            fcntl.flock(out, fcntl.LOCK_EX)
            out.write(json.dumps(dict(ts=time.time(), event=event, error=type(exc).__name__)) + '\n')
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        pass


def emit(home, event, task_id, *, turn=None, **fields):
    try:
        directory = home_path(home) / 'telemetry'
        directory.mkdir(parents=True, exist_ok=True)
        # events itself is the lock and sequence authority: no separate counter can drift.
        with (directory / 'events.jsonl').open('a+', encoding='utf-8') as out:
            fcntl.flock(out, fcntl.LOCK_EX)
            out.seek(0)
            seq = 0
            for line in out:
                seq = max(seq, json.loads(line)['seq'])
            if turn is None:
                value = os.environ.get('FACTORY_TURN', '')
                turn = int(value) if value.isdigit() else None
            record = sanitize(dict(fields, schema=SCHEMA, event=event, ts=time.time(),
                                   task_id=task_id, turn=turn, seq=seq + 1))
            out.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
            out.flush()
            os.fsync(out.fileno())
            return record
    except Exception as exc:
        error(home, event, exc)
    return None


def read_events(home=None, task_id=None, since=None):
    path = home_path(home) / 'telemetry/events.jsonl'
    if not path.is_file():
        return []
    threshold = None
    if since not in (None, ''):
        try:
            threshold = float(since)
        except ValueError:
            from datetime import datetime
            threshold = datetime.fromisoformat(str(since).replace('Z', '+00:00')).timestamp()
    result = []
    with path.open() as source:
        fcntl.flock(source, fcntl.LOCK_SH)
        for line in source:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if (task_id is None or record['task_id'] == task_id) and (threshold is None or record['ts'] > threshold):
                result.append(record)
    return result


@lru_cache(maxsize=None)
def release(capability):
    name = {'lab': 'lab_client', 'inspector': 'engine_inspector'}.get(capability.split('.')[0], capability.split('.')[0])
    folder = Path(__file__).with_name('ccs') / name
    if not (folder / 'cc.yaml').is_file():
        return dict(capsule=capability.split('.')[0], capsule_version=None, release_sha256=None)
    manifest = (folder / 'cc.yaml').read_text()
    values = dict(line.split(':', 1) for line in manifest.splitlines() if line.startswith(('id:', 'version:')))
    files = {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    digest = hashlib.sha256(''.join(f'{p}\0{h}\n' for p, h in files.items()).encode()).hexdigest()
    return dict(capsule=values['id'].strip(), capsule_version=values['version'].strip(), release_sha256=digest)


def call(home, task_id, capability, packet, result, started, *, replay=False, store=None, turn=None):
    try:
        identity = release(capability)
        packet = packet if isinstance(packet, dict) else {}
        evidence, artifacts = None, None
        if store is not None:
            evidence = store._db.execute('SELECT count(*) FROM evidence WHERE task_id=?', (task_id,)).fetchone()[0]
            artifacts = store._db.execute('SELECT coalesce(sum(size),0) FROM artifacts WHERE task_id=?', (task_id,)).fetchone()[0]
        clean_inputs = sanitize(packet.get('inputs', {}))
        return emit(home, 'cc.call', task_id, turn=turn, **identity, capability=capability,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    in_bytes=len(json.dumps(packet, ensure_ascii=False).encode()),
                    out_bytes=len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode()),
                    outcome=result['outcome'], error_code=result.get('error', {}).get('code'),
                    task_evidence_records=evidence, task_artifact_bytes=artifacts,
                    inputs=clean_inputs, resources=sanitize(packet.get('resources', {})),
                    inputs_redacted=clean_inputs != packet.get('inputs', {}), replay=replay)
    except Exception as exc:
        error(home, 'cc.call', exc)


def record(home, table, value):
    """Called only after the containing evidence transaction commits."""
    try:
        task_id = value['task_id']
        if table == 'attempts':
            history = value['history']
            latest = history[-1]
            if latest.get('state') != value['state']:
                return
            started, ended = value.get('started'), value.get('ended')
            queued = history[0]['created']
            emit(home, 'job.transition', task_id, attempt_id=value['attempt_id'], kind=value['kind'],
                 **{'from': latest.get('previous'), 'to': value['state']},
                 queue_wait_s=started - queued if started is not None else None,
                 run_s=(ended - started) if ended is not None and started is not None else None)
        elif table == 'decisions':
            emit(home, 'decision', task_id, rev=value['rev'], action_type=value['action'].get('type'),
                 evidence_id_count=len(value['evidence_ids']), reason_length=len(value.get('reason_for_change', '')),
                 component=value['action'].get('component'), image=value['action'].get('image'),
                 ratio=value['action'].get('ratio'), reason=value['action'].get('reason'))
        elif table == 'evaluations' or (table == 'observations' and value.get('kind') in {'build_result', 'lab_result', 'ab_result'}):
            event = 'evaluation' if table == 'evaluations' else value['kind'].replace('_', '.')
            values = value.get('values', value.get('inputs', {}).get('run', {}))
            details = values.get('details', {})
            checks = details.get('engagement_checks', {})
            emit(home, event, task_id, record_id=value.get('eval_id', value.get('obs_id')),
                 wall_s=values.get('wall_s', values.get('wall_seconds', values.get('build_wall_seconds'))),
                 gate=values.get('gate'), ratio=values.get('ratio'), aa_gap=values.get('aa_gap'),
                 output_class=values.get('output_class'), per_arm_ms=values.get('per_arm_ms'),
                 cache_hit=values.get('cache_hit'), ms_per_token=details.get('eval_ms_per_token'),
                 correctness=value.get('correctness', values.get('correctness')),
                 execution_outcome=value.get('execution_outcome', values.get('execution_outcome')),
                 engagement={'x': sum(v is True for v in checks.values()), 'y': len(checks)} if checks else None)
    except Exception as exc:
        error(home, table, exc)


def summary(events):
    groups = {}
    for e in events:
        if e['event'] == 'cc.call':
            groups.setdefault(e['capability'], []).append(e)
    capabilities = []
    for name, rows in sorted(groups.items()):
        durations = sorted(r['duration_ms'] for r in rows)
        percentile = lambda p: durations[max(0, math.ceil(len(rows) * p) - 1)]
        capabilities.append(dict(capability=name, calls=len(rows), p50_ms=percentile(.5), p95_ms=percentile(.95),
                                 max_ms=max(durations), mean_out_bytes=sum(r['out_bytes'] for r in rows)/len(rows),
                                 errors=sum(r['outcome'] != 'ok' for r in rows)))
    turns = [e for e in events if e['event'] == 'agent.turn']
    jobs = [e for e in events if e['event'] == 'job.transition']
    times = [(f"CC {name}", sum(e['duration_ms'] for e in rows)/1000) for name, rows in groups.items()]
    times += [(f"turn {e['task_id']}/{e['turn']}", e['duration_ms']/1000) for e in turns]
    times += [(f"job {e['attempt_id']}", e['run_s']) for e in jobs if e.get('run_s') is not None]
    return dict(capabilities=capabilities, turns=turns, jobs=jobs,
                where_time_went=[dict(label=n, seconds=s) for n, s in sorted(times, key=lambda x: -x[1])[:3]])


def show(home=None, task_id=None, since=None, as_json=False):
    result = summary(read_events(home, task_id, since))
    if as_json:
        print(json.dumps(result, indent=2))
        return
    print('Capability | calls | p50/p95/max ms | mean out bytes | errors')
    for r in result['capabilities']:
        print(f"{r['capability']} | {r['calls']} | {r['p50_ms']:.1f}/{r['p95_ms']:.1f}/{r['max_ms']:.1f} | {r['mean_out_bytes']:.1f} | {r['errors']}")
    print('Task / turn | duration ms | tool calls | tokens')
    for r in result['turns']:
        print(f"{r['task_id']}/{r['turn']} | {r['duration_ms']:.1f} | {r['tool_calls']} | {r['tokens']}")
    print('Job | transition | queue wait s | run s')
    for r in result['jobs']:
        print(f"{r['attempt_id']} | {r['from']} → {r['to']} | {r['queue_wait_s']} | {r['run_s']}")
    for r in result['where_time_went']:
        print(f"Where time went: {r['label']} {r['seconds']:.2f} s (overlapping spans)")


def set_turn_env(home=None, task_id=None):
    """Refresh inherited MCP environments from the controller's durable turn reservation."""
    try:
        task_id = task_id or os.environ.get('FACTORY_TASK_ID', '')
        if not task_id or Path(task_id).name != task_id:
            return
        path = home_path(home) / 'sessions' / (task_id + '.state.json')
        if path.is_file():
            os.environ['FACTORY_TURN'] = str(json.loads(path.read_text())['turns'])
    except Exception as exc:
        error(home, 'turn.context', exc)
