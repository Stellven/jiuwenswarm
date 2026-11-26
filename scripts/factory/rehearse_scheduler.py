"""Run real scheduler turns on the copy prepared by scheduler_dry_run_r8.sh."""
import json
import os
import subprocess
import sys
from pathlib import Path

from jiuwenswarm.factory import scheduler
from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.taskgraph import plan_get


def write(path, doc):
    path.write_text(json.dumps(doc, indent=1, default=str) + '\n')


def main(task, nodes):
    home = Path(os.environ['FACTORY_HOME'])
    out = home / 'dry-run'
    out.mkdir(exist_ok=True)
    store = Store(home)
    nodes = nodes or [n['node_id'] for n in plan_get(store, task)['nodes']]
    failed = []
    for node in nodes:
        write(out / f'{node}.brief.json', scheduler.finalize_brief(store, task, node))
        ready = {n['node_id'] for n in scheduler.next_work(store, task)['to_finalize']}
        preview = node not in ready
        env = dict(os.environ, FACTORY_SCHEDULER_PREVIEW=str(int(preview)))
        print(node, 'preview' if preview else 'admission', flush=True)
        old = store._db.execute('SELECT MAX(rowid) FROM observations').fetchone()[0] or 0
        with (out / f'{node}.agent.log').open('w') as log:
            result = subprocess.run([sys.executable, '-m', 'jiuwenswarm.factory.scheduler_agent',
                                     '--home', str(home), '--task', task, '--node', node],
                                    env=env, stdout=log, stderr=subprocess.STDOUT)
        kind = 'scheduler_dry_run_proposal' if preview else scheduler.FINAL_KIND
        rows = store._db.execute('SELECT "values" FROM observations WHERE rowid>? AND task_id=? AND kind=? ORDER BY rowid',
                                 (old, task, kind))
        proposals = [json.loads(row[0]) for row in rows]
        proposals = [p for p in proposals if p['node_id'] == node]
        write(out / f'{node}.proposals.json', proposals)
        if result.returncode or not proposals or not proposals[-1].get('validated', not preview):
            failed.append(node)
    if failed:
        raise SystemExit('Missing or refused proposals: ' + ', '.join(failed))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
