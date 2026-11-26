"""When the controller stops a run for an operator (a person or a repair agent), and the step checkpoints.

Halts (always on; thresholds from task constraints.halt_policy):
- a node output failed its node check `failed_checks_in_a_row` times in a row (default 2): the worker is not
  converging and someone should look before it spends more turns;
- a capped run failed on the machine or the host (codes in `infra_codes`: MACHINE_BUSY, MEMORY_LOW,
  UNEXPECTED, SERVER_EXIT, DISK, SOURCE, STATE), or the same recipe failed `failed_runs_in_a_row` times
  in a row on one node (default 2).

A halt writes FACTORY_HOME/HALT.md (what stopped, the evidence ids, how to resume), records a host observation
of kind operator_halt and pauses the run. Running the controller again acknowledges it: the same halt (same
evidence) does not fire twice, a new failure does.

Step checkpoints (constraints.halt_policy.step, or FACTORY_STEP=1): when a node's final contract is ready and
the node could run, the controller holds it (operator hold, reason "step checkpoint") and pauses. The operator
reads the final contract and releases the node (jiuwenswarm-factory release <task> <node> <reason>), then runs again.
"""
import json
import os
from pathlib import Path
import time

INFRA = ('MACHINE_BUSY', 'MEMORY_LOW', 'UNEXPECTED', 'SERVER_EXIT', 'DISK', 'SOURCE', 'STATE')
STEP_REASON = 'step checkpoint: the final node contract is ready; release the node to run it'


def policy(task):
    p = dict(failed_checks_in_a_row=2, failed_runs_in_a_row=2, infra_codes=list(INFRA), step=False)
    p.update((task.get('constraints') or {}).get('halt_policy') or {})
    if os.environ.get('FACTORY_STEP') == '1':
        p['step'] = True
    return p


def _observations(host, task_id, kind):
    rows = host._db.execute('SELECT obs_id, "values" FROM observations WHERE task_id=? AND kind=? ORDER BY created, rowid',
                            (task_id, kind))
    return [(obs_id, json.loads(values)) for obs_id, values in rows]


def find(host, task_id, graph_nodes, task):
    """Halts that apply now: [{key, node_id, reason, evidence}]."""
    p = policy(task)
    halts = []
    live = {n['node_id']: n for n in graph_nodes if n['state'] not in {'done', 'cancelled', 'superseded'}}
    streak = {}
    for obs_id, v in _observations(host, task_id, 'node_check'):
        if v.get('node_id') not in live or v.get('state') != 'finished':
            continue
        key = (v['node_id'], v.get('output', 'change'))
        streak[key] = [] if v.get('passed') else streak.get(key, []) + [obs_id]
    for (node_id, output), failed in streak.items():
        if len(failed) >= p['failed_checks_in_a_row']:
            halts.append(dict(key=f'checks:{node_id}:{output}:{failed[-1]}', node_id=node_id, evidence=failed,
                              reason=f'output {output} of {node_id} failed its node check {len(failed)} times in a row'))
    runs = {}
    for obs_id, v in _observations(host, task_id, 'capped_run'):
        node_id = v.get('node_id')
        error = v.get('error') or {}
        if v.get('outcome') != 'ok' and error.get('code') in p['infra_codes']:
            halts.append(dict(key=f'run:{obs_id}', node_id=node_id, evidence=[obs_id],
                              reason=f"capped {v.get('recipe')} run failed on the host: {error.get('code')}: "
                                     f"{str(error.get('message'))[:400]}"))
        if node_id in live:
            key = (node_id, v.get('recipe'))
            runs[key] = [] if v.get('outcome') == 'ok' else runs.get(key, []) + [obs_id]
    for (node_id, recipe), failed in runs.items():
        if len(failed) >= p['failed_runs_in_a_row']:
            halts.append(dict(key=f'runs:{node_id}:{recipe}:{failed[-1]}', node_id=node_id, evidence=failed,
                              reason=f'{len(failed)} {recipe} runs of {node_id} failed in a row'))
    return halts


def halt(store, task_id, state, halts):
    """Record the new halts (not already acknowledged); return them."""
    seen = set(state.get('halts_seen', []))
    new = [h for h in halts if h['key'] not in seen]
    if not new:
        return []
    state['halts_seen'] = sorted(seen | {h['key'] for h in new})
    for h in new:
        store.append_observation(task_id, dict(kind='operator_halt', values=dict(h, at=time.time()),
                                               host_run=dict(by='controller halt policy', module='jiuwenswarm.factory.halt_policy'),
                                               limitations='The run stopped for an operator; running it again acknowledges this halt.'))
    lines = [f'# Run halted: {task_id}', '', time.strftime('%Y-%m-%d %H:%M:%S'), '']
    for h in new:
        lines += [f"- **{h.get('node_id') or 'task'}**: {h['reason']}", f"  evidence: {', '.join(h['evidence'])}"]
    lines += ['', 'To look: `jiuwenswarm-factory status <task> --plain`, the evidence above (factory evidence read), '
              'controller.log and FACTORY_HOME/runs/<attempt>/progress.log.',
              'To repair: fix the cause (a capsule, the machine, an operator note to the agent, or reopen the node).',
              'To resume: run the controller again; this halt is then acknowledged and does not fire again.']
    Path(store.home, 'HALT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return new


def step_holds(store, task_id, state, runnable):
    """Hold each runnable node once (its first step checkpoint); returns the nodes held now."""
    from .taskgraph import operator_patch
    held = []
    stepped = set(state.get('stepped', []))
    for item in runnable:
        node_id = item['node_id']
        if node_id in stepped or item.get('state') == 'running':
            continue
        operator_patch(store, task_id, 'hold', node_id, STEP_REASON)
        stepped.add(node_id)
        held.append(node_id)
    state['stepped'] = sorted(stepped)
    if held:
        Path(store.home, 'STEP.md').write_text(
            f'# Step checkpoint: {task_id}\n\nHeld before it runs: {", ".join(held)}.\n\n'
            'Read the final node contract (status --plain, or the node_contract_final record), then release:\n'
            + ''.join(f'    jiuwenswarm-factory release {task_id} {n} "step checkpoint passed"\n' for n in held)
            + '\nand run the controller again.\n', encoding='utf-8')
    return held
