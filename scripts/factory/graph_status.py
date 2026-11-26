"""One screen of a factory graph run: controller state, operator pause and notes, nodes, final contracts, capped runs,
halts and step checkpoints.

    FACTORY_HOME=... python scripts/factory/graph_status.py <task_id> [--brief]

Prints RUNNING, PAUSED (with the reason) or EXITED on the first line so a monitor can grep it.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from jiuwenswarm.factory.store import Store


def main(task_id, brief=False):
    home = Path(os.environ['FACTORY_HOME'])
    store = Store(home)
    state_path = home / 'sessions' / f'{task_id}.state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    alive = subprocess.run(['pgrep', '-f', f'muse_v3_controller.py {task_id}'], capture_output=True).returncode == 0
    outcome = state.get('outcome')
    from jiuwenswarm.factory.run_pause import current, describe
    pause = current(store, task_id)
    if pause:  # an operator pause: a running controller stops at its next check
        head = 'PAUSED (stopping at its next check)' if alive else 'PAUSED'
        reason = describe(pause)
    else:
        head = 'RUNNING' if alive else ('PAUSED' if outcome == 'paused' else f'EXITED outcome={outcome}')
        reason = state.get('stop_reason') or ''
    print(head, '|', reason[:300], '| turns', state.get('turns'))
    from jiuwenswarm.factory.operator_notes import pending
    for note in pending(home, task_id, state):
        print('operator note (not yet read by the agent):', time.strftime('%H:%M:%S', time.localtime(note['created'])),
              note['text'][:200])
    from jiuwenswarm.factory.taskgraph import plan_get
    nodes = plan_get(store, task_id)['nodes']
    finals = {json.loads(v)['node_id'] for (v,) in store._db.execute(
        'SELECT "values" FROM observations WHERE task_id=? AND kind=?', (task_id, 'node_contract_final'))}
    print('nodes:', ' '.join(f"{n['node_id']}={n['state']}{'*' if n['node_id'] in finals else ''}{'(held)' if n.get('hold') else ''}"
                             for n in nodes))
    for row in store._db.execute('SELECT attempt_id, kind, state, request, started, ended FROM attempts WHERE task_id=? '
                                 'ORDER BY rowid DESC LIMIT 4', (task_id,)):
        attempt_id, kind, st, req, started, ended = row
        req = json.loads(req)
        took = f"{((ended or time.time()) - started) / 60:.0f} min" if started else ''
        print(f"run {attempt_id[:8]} {kind} {req.get('recipe', '')} {req.get('name', req.get('label', ''))} "
              f"node={req.get('node_id')} {st} {took}")
        if st in ('queued', 'running') and not brief:
            progress = home / 'runs' / attempt_id / 'progress.log'
            if progress.exists():
                for line in progress.read_text(errors='replace').splitlines()[-3:]:
                    print('   ', line[:200])
    for kind in ('operator_halt', 'node_contract_refusal', 'operator_pause', 'attempt_excused'):
        for (v,) in store._db.execute('SELECT "values" FROM observations WHERE task_id=? AND kind=? ORDER BY created DESC LIMIT 2',
                                      (task_id, kind)):
            v = json.loads(v)
            print(kind, v.get('action') or v.get('node_id'), v.get('by') or '',
                  (v.get('reason') or '; '.join(v.get('problems') or []))[:300])
    for name in ('PAUSE.md', 'HALT.md', 'STEP.md'):
        if (home / name).exists():
            print(f'--- {name}:', ' '.join((home / name).read_text().split())[:400])
    checks = list(store._db.execute('SELECT "values" FROM observations WHERE task_id=? AND kind=? ORDER BY created DESC LIMIT 3',
                                    (task_id, 'node_check')))
    for (v,) in checks:
        v = json.loads(v)
        print('check', v.get('node_id'), v.get('output'), v.get('state'), 'passed' if v.get('passed') else 'NOT passed',
              (v.get('summary') or v.get('reason') or '')[:160])


if __name__ == '__main__':
    main(sys.argv[1], '--brief' in sys.argv)
