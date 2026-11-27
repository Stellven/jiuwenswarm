"""Operator entry point to the independent Run 4 capped lab queue."""
import argparse
import os
from pathlib import Path

from jiuwenswarm.factory import api
from jiuwenswarm.factory.muse_r11_cache import ROOT, TASK, RECIPE
from jiuwenswarm.factory.muse_r11_target import ARMS
from jiuwenswarm.factory.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    aliases = {'control': 'AQBC', 'seeded': 'AQBCE'}
    parser.add_argument('arm', choices=['profile', *ARMS, *aliases])
    args = parser.parse_args()
    arm = aliases.get(args.arm, args.arm)
    graph_home = ROOT/'r11/graph'
    if not (graph_home/'factory.sqlite').is_file():
        raise ValueError('Native Run 4 graph has not been admitted.')
    graph = Store(graph_home)
    factory = graph.get_task('muse-2bit-demo-r11')
    if factory.get('contract_id') != 'muse-2bit-demo-r11':
        raise ValueError('Unexpected native factory contract')
    home = ROOT/'r11/lab-home'
    os.environ['PYTHONPATH'] = str(Path(__file__).resolve().parents[2])
    os.environ['JOBQ_DIR'] = str(ROOT/'r9/graph/lab-state/jobq')
    store = Store(home)
    if not store._db.execute('SELECT task_id FROM tasks WHERE task_id=?', (TASK,)).fetchone():
        store.create_task(dict(task_id=TASK, objective='Measure the real Run 4 cache premise and eligible candidate',
                               allowed_effects=['process.exec'], constraints=dict(model_runs=True,
                               attempt_limits={'model_run':3}), resources=dict(memory_cap='96G',
                               floor_gib=8, need_available_gib=100, device_budget_mib=110000)))
    result = api.dispatch(store.scoped(TASK), TASK, 'capped_runner.start', dict(inputs=dict(
        recipe=RECIPE, args={'arm':arm}, idem_key='run4-'+arm)))
    print(result)


if __name__ == '__main__':
    main()
