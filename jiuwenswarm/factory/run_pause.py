"""Run-wide operator pause: stop a task's controller cleanly at its next check, fix the run, then resume.

``pause`` and ``resume`` are host operator records (observations of kind ``operator_pause``, written only by the
host CLI, never by the agent). The latest record decides: a run is paused while its latest record is a pause.
FACTORY_HOME/PAUSE.md tells a person what is paused, why, by whom and since when, and how to resume.

The controller looks for a pause at the top of every loop iteration, while it waits on active jobs, before the
scheduler agent finalizes a node and before every agent turn. It then stops with outcome ``paused`` and a
stop_reason naming the pause. Running jobs are left to finish (``--cancel-jobs`` cancels them through the
controller's ordinary cancel path); the next run reconciles them. While paused every operator fix works:
revise, note, hold, release, reopen, excuse, retire.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

KIND = 'operator_pause'
FILE = 'PAUSE.md'


def records(host, task_id):
    rows = host._db.execute('SELECT obs_id, "values" FROM observations WHERE task_id=? AND kind=? ORDER BY created, rowid',
                            (task_id, KIND))
    return [dict(json.loads(values), obs_id=obs_id) for obs_id, values in rows]


def current(host, task_id):
    """The pause record in force, or None."""
    found = records(host, task_id)
    return found[-1] if found and found[-1]['action'] == 'pause' else None


def current_in(data):
    """The pause in force from a store dump or read-only snapshot (status without the live store)."""
    task_id = data['tasks'][0]['task_id']
    rows = [dict(r['values'], obs_id=r['obs_id']) for r in data.get('observations', [])
            if r.get('kind') == KIND and r.get('task_id', task_id) == task_id]
    rows.sort(key=lambda r: r.get('at', 0))
    return rows[-1] if rows and rows[-1]['action'] == 'pause' else None


def describe(record):
    return (f"paused by {record['by']} at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record['at']))}: "
            f"{record['reason']}")


def _write(host, task_id, record):
    lines = [f'# Run paused: {task_id}', '', describe(record), '',
             'Running jobs were ' + ('cancelled.' if record.get('cancel_jobs') else 'left to finish; the next run records them.'),
             '', 'While paused, fix the run with the operator commands (all record host operator records):',
             f'    jiuwenswarm-factory revise {task_id} "<reason>" [--dry-run]   # apply the current contract revision',
             f'    jiuwenswarm-factory note|hold|release|reopen|retire|excuse {task_id} ...',
             '', 'Then resume (lifts the pause and runs the controller again):',
             f'    jiuwenswarm-factory resume {task_id} "<reason>"', '']
    Path(host.home, FILE).write_text('\n'.join(lines), encoding='utf-8')


def _record(host, task_id, values):
    host.get_task(task_id)
    row = host.append_observation(task_id, dict(
        kind=KIND, values=values, host_run=dict(by=values['by'], module='jiuwenswarm.factory.run_pause'),
        limitations='Operator record: pauses or resumes the controller of this task; it changes no evidence.'))
    return dict(row['values'], obs_id=row['obs_id'])


def pause(host, task_id, reason, by='operator', cancel_jobs=False):
    """Record a pause (once: pausing a paused run returns the pause in force)."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('Say why the run is paused')
    now = current(host, task_id)
    if now:
        return dict(now, already=True)
    record = _record(host, task_id, dict(action='pause', reason=reason.strip(), by=by, at=time.time(),
                                         cancel_jobs=bool(cancel_jobs)))
    _write(host, task_id, record)
    return record


def resume(host, task_id, reason='', by='operator'):
    """Record the end of the pause in force; None when the run is not paused."""
    now = current(host, task_id)
    if not now:
        return None
    record = _record(host, task_id, dict(action='resume', reason=(reason or '').strip() or 'resumed by operator', by=by,
                                         at=time.time(), pause=now['obs_id']))
    path = Path(host.home, FILE)
    if path.exists() and path.read_text(encoding='utf-8').startswith(f'# Run paused: {task_id}\n'):
        path.unlink()
    return record
