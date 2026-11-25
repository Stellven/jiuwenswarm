"""Generate factory/contracts/muse-q2-ttft-v3.json: the Muse demo as preliminary node contracts.

Revision 4 of the Muse demo contract. The planner's node contracts become preliminary: each keeps its
goal, ports, dependencies, criteria and ceilings, and gains slots the scheduler agent fills just
before the node runs (which capsules to bind, and where the evidence allows, concrete numbers and
criteria). Pinned verifier inputs the scheduler may tighten carry a direction in ``bounds``.
Nothing here may be loosened by the scheduler (node_finalize.check_final).

Reads muse-q2-ttft-v2.json (make_muse_q2_contract.py) and writes the v3 contract and its plan file.
"""
import copy
import json
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = REPO / 'jiuwenswarm/factory/contracts'
source = json.loads((OUT / 'muse-q2-ttft-v2.json').read_text(encoding='utf-8'))
contract = copy.deepcopy(source)
contract.update(contract_id='muse-q2-ttft-v3', version=5)
contract['provenance']['notes'].append(
    'Revision 4 (v3 file) makes every node contract preliminary: the scheduler agent finalizes each node just before it '
    'runs, binding capsules and filling slots from accepted upstream outputs, earlier failures and the machine state. '
    'A final contract may be more concrete or stricter than its preliminary one, never weaker.')

contract['provenance']['notes'].append(
    'Revision 5: the scheduler agent reported a spec gap on pin_inputs (2026-11-25): the free disk criterion asked for '
    '1.4 TB, the room both packs need, while a run that reuses the packs writes almost nothing. The planner states it as '
    'free disk covering what the run writes plus 100 GB.')
# Planner revisions of v2 node criteria (a weakening is the planner's call, never the scheduler's).
REVISED = {
    ('pin_inputs', 'Records free disk at least 1.4 TB, the cgroup memory cap and the available memory before any load.'):
        'Records free disk, the disk this run will write, the cgroup memory cap and the available memory before any load; '
        'free disk covers what the run writes plus 100 GB (about 1.4 TB when the NVFP4 and Q2 packs are both written).',
}
BIND = dict(id='bind', at='work.bound_ccs', kind='ccs',
            **{'from': 'The capsule catalog, what the upstream nodes were built with and what failed before for this node.'})
EXTRA_ELIGIBLE = {
    # The time-to-first-token node may also draw on the decode fill and expert streaming capsules; the
    # scheduler sees that the decode fill measured negative on arm E and decides what to bind.
    'port_ttft_cache': ['engine.build_expert_fill', 'engine.expert_streaming'],
}
SLOTS = {
    'requant_q2': [dict(id='size_criterion', at='outputs.q2_pack.criteria', kind='criteria',
                        **{'from': 'The census of the accepted NVFP4 pack and the disk grant: one criterion naming the expected Q2 size.'})],
    'measure_accuracy': [dict(id='checkpoints', at='outputs.accuracy.criteria', kind='criteria',
                              **{'from': 'The time left in the node limits and the measured seconds per question on E0: one criterion naming the planned checkpoints.'})],
    'port_ttft_cache': [dict(id='decode_floor', at='outputs.change.criteria', kind='criteria',
                             **{'from': 'Earlier measured decode rates of arms B, C and E: one criterion that the change must not lower decode.'})],
    'size_prefill_batch': [dict(id='batch_choice', at='outputs.batch_plan.criteria', kind='criteria',
                                **{'from': 'The measured KV and compute buffers at each micro-batch size and the free memory now: one criterion naming the micro-batch sizes to try.'})],
}
BOUNDS = {
    'ingest_nvfp4': {'verifiers.nvfp4_pack.inputs.expect_bytes_range': 'inside'},
    'requant_q2': {'verifiers.q2_pack.inputs.expect_bytes_range': 'inside'},
    'measure_accuracy': {'verifiers.accuracy.inputs.margin_pts': 'lower', 'verifiers.accuracy.inputs.min_letter_mass': 'higher'},
    'size_prefill_batch': {'verifiers.batch_plan.inputs.device_budget_mib': 'lower',
                           'verifiers.batch_plan.inputs.min_agree_chars': 'higher'},
}
for node in contract['extensions']['factory.node-contracts']['nodes']:
    key = node['node_id']
    for output in node['outputs']:
        output['criteria'] = [REVISED.get((key, c), c) for c in output.get('criteria', [])]
    node['stage'] = 'preliminary'
    work = node.setdefault('work', {})
    work['eligible_ccs'] = list(dict.fromkeys(work.get('helpful_ccs', []) + EXTRA_ELIGIBLE.get(key, [])))
    node['slots'] = [BIND] + SLOTS.get(key, [])
    if key in BOUNDS:
        verifiers = {v['output']: v for v in node['verifiers']}
        for path in BOUNDS[key]:
            _, output, _, name = path.split('.')
            assert name in (verifiers[output].get('inputs') or {}), path
        node['bounds'] = BOUNDS[key]

plan = {'format': 'factory.plan/1', 'planner': 'hand-written demo plan (muse-q2-ttft, preliminary node contracts)',
        'nodes': [{'node_id': n['node_id'], 'node_contract': n['node_id'], 'depends_on': n.get('predecessors', []),
                   'title': n['objective']} for n in contract['extensions']['factory.node-contracts']['nodes']]}
(OUT / 'muse-q2-ttft-v3.json').write_text(json.dumps(contract, indent=1) + '\n', encoding='utf-8')
(OUT.parent / 'tasks/muse-q2-ttft-v3.plan.json').write_text(json.dumps(plan, indent=1) + '\n', encoding='utf-8')
assert all(old not in json.dumps(contract) for _, old in REVISED), 'a revised criterion was not found'
print('wrote', len(plan['nodes']), 'preliminary nodes')
