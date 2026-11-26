"""Generate the rehearsal contract muse-2bit-rehearsal-r1: the new parts of the v4 graph on the tiny Muse test pack.

Before the first end-to-end run, JiuwenSwarm agents work a small graph through the same machinery: the scheduler
agent finalizes each node and binds capsules, the working agent runs everything through factory.capped_runner,
capsule verifiers and an independent reviewer check every output, the halt policy and the step checkpoints stop
the run for the operator. The test pack is a 4-layer, 16-expert Muse built from random weights: its text is not
meant to be coherent, and the criteria say so.

    python scripts/factory/make_muse_rehearsal.py <repo>
"""
import copy
import json
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = REPO / 'jiuwenswarm/factory/contracts'
TARGET = 'iq2_xxs,down=q2_k'
v4 = json.loads((OUT / 'muse-2bit-ttft-v4.json').read_text(encoding='utf-8'))
contract = copy.deepcopy(v4)
contract.update(contract_id='muse-2bit-rehearsal-r1', version=1,
                title='Rehearsal of the Muse v4 graph on the tiny Muse test pack (random weights)')
contract['provenance']['notes'].append(
    'Rehearsal r1 (2026-11-25): the capped runs, the mixed 2-bit requantization, the routing trace and the paired '
    'accuracy recipe on the tiny Muse test pack, through the scheduler agent, capsule verifiers, reviews, the halt '
    'policy and step checkpoints. Test data, not a measurement of the model.')
BIND = dict(id='bind', at='work.bound_ccs', kind='ccs',
            **{'from': 'The capsule catalog, what the upstream nodes were built with and what failed before for this node.'})
RUN_CEILING = {'effects': ['process.exec', 'workspace.read', 'workspace.write'], 'workspace': 'read'}


def node(node_id, kind, objective, requirement_ids, predecessors, inputs, outputs, verifiers, limits, helpful, hands_to):
    return dict(node_id=node_id, kind=kind, objective=objective, requirement_ids=requirement_ids, predecessors=predecessors,
                inputs=inputs, outputs=outputs, evidence_obligations=['captured_input_and_output', 'invocation_observation'],
                node_limits=limits, authority_ceiling=copy.deepcopy(RUN_CEILING),
                work=dict(helpful_ccs=helpful, eligible_ccs=list(dict.fromkeys(helpful + ['factory.capped_runner', 'factory.engine_inspector']))),
                verifiers=verifiers, hands_to=hands_to, stage='preliminary', slots=[BIND])


nodes = [
    node('build_engine', 'build',
         'Build the stock engine (the owned checkout at the base commit) for GB10 with CUDA - llama-server, '
         'llama-quantize and llama-imatrix - and smoke it on the tiny Muse NVFP4 test pack.',
         ['A', 'cold_smoke'], [], [dict(name='source', **{'from': 'task:source'})],
         [dict(name='build', kind='evidence', criteria=[
             'A capped_run build record of the base commit 9048bad8 with CUDA architecture 121 and the three binaries '
             'with their sha256.']),
          dict(name='smoke', kind='evidence', criteria=[
              'One capped serve run of the tiny NVFP4 test pack answers two prompts with generated tokens and keeps '
              'its -lv 4 load log; the pack has random weights, so the text is not expected to be coherent.',
              'The run record names the memory cap, the peak cgroup memory and the lowest available memory.'])],
         [dict(output='build', review=True), dict(output='smoke', review=True)],
         {'turns': 15, 'build_attempts': 2, 'gpu_launches': 2}, ['factory.capped_runner'], 'requant_tiny'),
    node('requant_tiny', 'build',
         'Write a precision recipe and requantize the tiny NVFP4 test pack to the mixed 2-bit format: routed gate '
         'and up experts to IQ2_XXS and down experts to Q2_K, everything else kept at its source type.',
         ['B', 'pack_2bit_census'], ['build_engine'], [dict(name='build', **{'from': 'build_engine.build'})],
         [dict(name='recipe', kind='evidence', criteria=[
             'Names the source pack digest, the target type per tensor role and the imatrix digest; every chosen type '
             'has a GB10 kernel.',
             "Times one layer with the recipe's probe before the full run and records the projected full time."]),
          dict(name='pack_2bit', kind='evidence', criteria=[
              'Every routed gate and up expert weight is IQ2_XXS and every down expert weight Q2_K; every other tensor '
              'keeps its source type; .scale tensors carried unchanged.',
              'Two prompts on the 2-bit pack give tokens; top-1 token agreement with the NVFP4 test pack is reported, '
              'not claimed (random weights).'])],
         [dict(output='recipe', verifier='weights.build_weight_pack_compiler.verify_recipe', stage='fixture',
               review=True, inputs={'target': TARGET}),
          dict(output='pack_2bit', verifier='weights.build_weight_pack_compiler.verify_pack',
               stage='native CC execution', review=True,
               inputs={'target': TARGET, 'expect_bytes_range': [100_000_000, 1_000_000_000]})],
         {'turns': 25, 'gpu_launches': 4}, ['weights.build_weight_pack_compiler', 'factory.capped_runner'], 'trace_profile'),
    node('trace_profile', 'measure',
         'Record which experts the tiny 2-bit pack routes to on the calibration prompts (routing trace) and rank '
         'them into a seeded expert cache profile.',
         ['C'], ['requant_tiny'], [dict(name='pack_2bit', **{'from': 'requant_tiny.pack_2bit'}),
                                   dict(name='calibration', **{'from': 'contract:calibration_prompts'})],
         [dict(name='profile', kind='evidence', criteria=[
             'Per layer and expert hit counts for prompt and decode phases, from the routing trace, with the prompt '
             'set digest.',
             'A seeded cache profile (spark-expert-residency-nominations/1) written from that trace.'])],
         [dict(output='profile', review=True)],
         {'turns': 15, 'gpu_launches': 2}, ['analysis.expert_routing_profile', 'factory.capped_runner'], 'accuracy_tiny'),
    node('accuracy_tiny', 'measure',
         'Run the paired accuracy recipe on the tiny test packs - NVFP4 as the reference arm, 2-bit as the candidate '
         '- to the first planned checkpoint.',
         ['B'], ['requant_tiny', 'build_engine', 'trace_profile'],
         [dict(name='pack_2bit', **{'from': 'requant_tiny.pack_2bit'})],
         [dict(name='accuracy', kind='evidence', criteria=[
             'A muse-paired-accuracy/1 state with both arms scored on the same first 50 questions of the seeded '
             'order on real capped server loads; eval.paired_accuracy.verify is run on it and its result reported. '
             'No accuracy decision is claimed: the weights are random.'])],
         [dict(output='accuracy', review=True)],
         {'turns': 15, 'gpu_launches': 2}, ['eval.paired_accuracy', 'factory.capped_runner'], 'deliver_to_lab'),
]
deliver = copy.deepcopy(next(n for n in v4['extensions']['factory.node-contracts']['nodes'] if n['node_id'] == 'deliver_to_lab'))
deliver.update(predecessors=['accuracy_tiny'], inputs=[dict(name='accuracy', **{'from': 'accuracy_tiny.accuracy'})],
               objective='Rehearsal end: held by the operator; the rehearsal does not send anything to the lab.')
nodes.append(deliver)
contract['extensions']['factory.node-contracts']['nodes'] = nodes
plan = {'format': 'factory.plan/1', 'planner': 'hand-written rehearsal plan (muse-2bit-rehearsal-r1)',
        'nodes': [{'node_id': n['node_id'], 'node_contract': n['node_id'], 'depends_on': n['predecessors'],
                   'title': n['objective']} for n in nodes]}
(OUT / 'muse-2bit-rehearsal-r1.json').write_text(json.dumps(contract, indent=1) + '\n', encoding='utf-8')
(OUT.parent / 'tasks/muse-2bit-rehearsal-r1.plan.json').write_text(json.dumps(plan, indent=1) + '\n', encoding='utf-8')

task = json.loads((OUT.parent / 'tasks/muse-2bit-ttft-v4.json').read_text(encoding='utf-8'))
task.update(task_id='muse-2bit-rehearsal-r1', contract_id='muse-2bit-rehearsal-r1', plan='muse-2bit-rehearsal-r1.plan.json',
            budget={'max_turns': 80, 'wall_clock_s': 21600})
task['objective'] = ('Rehearsal on the tiny Muse test pack (random weights, test data): work every node of contract '
                     'muse-2bit-rehearsal-r1 - build the stock engine and smoke it, requantize the tiny NVFP4 pack to the '
                     'mixed 2-bit format, trace its routing into a seeded cache profile, and run the paired accuracy '
                     'recipe to its first checkpoint. Before each node the scheduler agent finalizes its contract and '
                     'binds its capsules; everything that executes runs through factory.capped_runner.')
task['operator_labels'] = {'run': 'Rehearsal on test fixtures (tiny random-weight Muse pack); not a measurement of the model.'}
res = task['resources']
res['need_available_gib'] = 20
res['verifier_inputs'].update(
    tiny_nvfp4_pack='${FACTORY_MUSE_CAPS}/tiny/tiny-nvfp4-f32.gguf',
    tiny_imatrix='${FACTORY_MUSE_CAPS}/tiny/imatrix-tiny.gguf',
    note='Rehearsal: the tiny test pack and its imatrix (made by the operator with llama-imatrix on the tiny pack) stand in '
         'for the real packs; checkpoint_index and imatrix are the real ones and are not used here.')
res.pop('operator_inputs', None)
res['capsules'] = [c for c in res['capsules'] if c not in {'weights.build_muse_nvfp4_reader', 'weights.build_expert_scale_wiring',
                                                           'engine.build_expert_weight_cache', 'engine.size_prefill_batch'}]
task['component_cc'] = 'weights.build_weight_pack_compiler'
task['source']['branch'] = 'rehearsal'
(OUT.parent / 'tasks/muse-2bit-rehearsal-r1.json').write_text(json.dumps(task, indent=1) + '\n', encoding='utf-8')
print('wrote muse-2bit-rehearsal-r1', [n['node_id'] for n in nodes])
