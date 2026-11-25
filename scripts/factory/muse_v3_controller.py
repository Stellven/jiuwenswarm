"""Run the Muse v3 graph with the factory controller, plus one operator test of the never-weaker rule.

Before the scheduler agent's first try on measure_accuracy, the operator proposes a final contract
that loosens the paired accuracy margin from 5 to 8 points (a weaker contract). Control code must
refuse it; the refusal is recorded with by = operator-test and the scheduler agent sees it in its
brief. Then the scheduler agent finalizes the node as usual. Nothing else differs from
``jiuwenswarm-factory run``.

    python scripts/factory/muse_v3_controller.py muse-q2-ttft-v3 --grant process.exec ...
"""
import argparse
import asyncio
import json
import os

from jiuwenswarm.factory import scheduler
from jiuwenswarm.factory.controller import Controller
from jiuwenswarm.factory.node_contract import for_task, node as contract_node
from jiuwenswarm.factory.node_finalize import draft_final
from jiuwenswarm.factory.scheduler_agent import run_subprocess

TESTS = {'measure_accuracy'}


def weaker_accuracy(store, task_id, node_id):
    task = store.get_task(task_id)
    graph_node = next(n for n in scheduler._graph(store, task_id)['nodes'] if n['node_id'] == node_id)
    final = draft_final(contract_node(for_task(task), graph_node['node_contract']))
    final['work']['bound_ccs'] = ['eval.paired_accuracy']
    final['outputs'][0]['criteria'].append('Checkpoints at 50, 100, 160, 250 and 430 questions.')
    final['verifiers'][0]['inputs']['margin_pts'] = 8  # the weakening under test: 5 -> 8 points
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('task_id')
    parser.add_argument('--grant', action='append', default=[])
    args = parser.parse_args()
    home = os.environ['FACTORY_HOME']
    controller = Controller(home, grants=args.grant)
    store = controller.store

    def runner(home_, task_id, node_id, attempt=1):
        if node_id in TESTS and attempt == 1:
            result = scheduler.finalize(store, task_id, node_id, weaker_accuracy(store, task_id, node_id),
                                        'Operator test of the never-weaker rule: loosen the paired accuracy margin '
                                        'from 5 to 8 points.', by='operator-test')
            print(json.dumps(dict(operator_test=node_id, admitted=result['admitted'],
                                  problems=result.get('problems')), indent=1), flush=True)
            if result['admitted']:
                raise SystemExit('the weaker operator test contract was admitted: stop and look')
        return run_subprocess(home_, task_id, node_id, attempt)

    controller.scheduler = runner
    print(json.dumps(asyncio.run(controller.run(args.task_id)), default=str, indent=1))


if __name__ == '__main__':
    main()
