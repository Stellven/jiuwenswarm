"""Generate the eight-node Muse demo from the checked-in revision 8 contract."""
import json
import sys
from pathlib import Path


BASE = 'muse-2bit-ttft-v4'
TASK = 'muse-2bit-demo-r8'
REPLAY = ('The two full weight production steps already ran twice. Verify their recorded outputs '
          'with read-only manifest, shard size and header census checks. Record the original job and '
          'duration separately from the verification time. All other work runs in this demo.')
CONVERT = '1a040f7126cb485581b3b317932290f4'
QUANTIZE = 'b117d0f1e0e3428ebba1b7c681277d8b'


def generate(root):
    factory = root / 'jiuwenswarm/factory'
    contracts, tasks = factory / 'contracts', factory / 'tasks'
    contract = json.loads((contracts / f'{BASE}.json').read_text())
    task = json.loads((tasks / f'{BASE}.json').read_text())
    assert contract['version'] == 8
    contract['contract_id'] = TASK
    contract['purpose'] += ' ' + REPLAY
    contract['provenance']['notes'] = [f'Derived from {BASE} revision 8.', REPLAY]
    document = contract['extensions']['factory.node-contracts']
    nodes = {n['node_id']: n for n in document['nodes'] if n['node_id'] != 'record_profile'}
    document['nodes'] = list(nodes.values())
    pins = nodes['pin_inputs']
    pins['briefing'] = dict(summary='Pin the stock source and inputs before working the converter.',
        how_to_fill=['Bind the reader for inspect_scale_layout (read-only index and shard headers). Use the '
                     'operator checkpoint_digests, contract prompt pins and host_reading for the remaining criteria.'])
    pins['outputs'][0]['criteria'][1] = ('Record free disk, expected new writes, cgroup cap and available memory. '
                                         'Allow 100 GB free beyond new writes. The two packs are linked read-only.')
    ingest = nodes['ingest_nvfp4']
    ingest['objective'] = ('Implement the converter in the owned checkout, test it on the tiny fixture, '
                           'and verify the recorded full NVFP4 conversion through capped_runner replay.')
    ingest['briefing'] = dict(summary=REPLAY, facts=[
        f'{BASE} conversion: capped_runner replay.job_id={CONVERT} (original attempt, not queue id), producer 6eeca78bd8c74744b8d6bc04b9eaf151dc089195, bf16, 50G splits.',
        'The fixture exercises the fresh implementation. The recorded producer owns the production pack.'])
    requant = nodes['requant_2bit']
    requant['authority_ceiling']['workspace'] = 'write'
    requant['objective'] = ('Plan and verify the mixed precision recipe, replay the matching production quantization '
                            'through capped_runner, then run the real E0 smoke on the accepted pack.')
    requant['outputs'][0]['criteria'][1] = ('Match the production receipt to the source digest, imatrix, target '
                                            'and quantizer commit. Report its original elapsed time and replay time.')
    requant['briefing'] = dict(summary=REPLAY, facts=[
        f'{BASE} full quantization: capped_runner replay.job_id={QUANTIZE} (original attempt, not queue id), producer cd8937e4f2bdd85f2a3a1e165ea73bc0df32f46f.',
        'Use IQ2_XXS for gate and up, Q2_K for down. Preserve all eight real smoke prompts.'])
    for n, output in [(ingest, 1), (requant, 1)]:
        n['outputs'][output]['criteria'].append('Cite the successful host replay receipt and original production job.')
    for node_id, maximum in [('build_base_engine', 1), ('requant_2bit', 1), ('size_prefill_batch', 2)]:
        nodes[node_id]['node_limits']['gpu_launches'] = maximum
    prefill = nodes['size_prefill_batch']
    prefill['briefing']['pitfalls'].append(
        'Two loads are approved: default and planned. If the verified budget needs a retune, stop at the '
        'checkpoint and ask the operator before another load. Keep the failed measurement.')
    wiring = nodes['wire_expert_scales']
    wiring['briefing'] = dict(summary='Implement and verify expert scales in the fresh owned checkout.',
        facts=['The operator approved seven tiny CPU processes once: two parity, three KLD including the '
               'stock control and two slice callbacks, in one 96 GiB capped scope after the machine gate.'],
        how_to_fill=['Bind expert_scale_wiring, source_workbench and capped_runner. For the change output call '
                     'factory.node_check.start on the owned checkout and omit verifier_inputs. The host submits '
                     'the one-shot wire_fixture job, verifies the pinned tiny packs and records the capped attempt. '
                     'Do not invoke the verifier directly.'])
    for n in nodes.values():
        for v in n.get('verifiers', []):
            if v.get('verifier') and v.get('review') is True:
                v['review'] = 'advisory'
    delivery = nodes['deliver_to_lab']
    delivery['objective'] = delivery['objective'].replace('both pack manifests and the routing profile', 'both replayed pack manifests')
    delivery['predecessors'].remove('record_profile')
    delivery['inputs'] = [i for i in delivery['inputs'] if i['name'] != 'profile']
    image = nodes['build_image']['briefing']
    image['facts'][0] = ('The original Nov 26 E0 build took about four minutes. Resolve the fresh checkout commit '
                         'and binary digest from this run’s base_engine evidence.')
    image['facts'][2] = 'Both manifests come from verified replay receipts. Treat linked packs as read-only.'
    image['how_to_fill'] = ['Bind factory.builder for the image and cite verified manifests from upstream replays.']
    plan = dict(format='factory.plan/1', planner='Muse demo revision 8', nodes=[
        dict(node_id=k, node_contract=k, depends_on=n.get('predecessors', []), title=n['objective'])
        for k, n in nodes.items()])
    task.update(task_id=TASK, contract_id=TASK, objective=contract['purpose'], plan=f'{TASK}.plan.json')
    stem = task['resources']['pack_stem']
    def first(pack):
        return f'{pack}/{stem}-{pack}-00001-of-00011.gguf'
    task['constraints']['approved_model_packs'] = {
        'build_base_engine': first('muse-nvfp4-v4'),
        'requant_2bit': first('muse-2bit-v4'), 'size_prefill_batch': first('muse-2bit-v4')}
    task['constraints']['halt_policy']['step'] = True
    task['constraints']['model_execution'] = ('Use capped_runner for production replays, builds and every model load. '
                                               'Every load requires the machine gate, 96 GiB cap and operator approval.')
    task['constraints']['workspace_files'] = ('Write working files under resources.verifier_inputs.work_dir. '
                                              'Linked production packs and manifests are read-only.')
    task['operator_labels']['run'] = REPLAY
    task['resources']['read_roots'] += ['${FACTORY_MUSE_DEMO}/pins', '${FACTORY_MUSE_DEMO}/graph-v4/packs']
    task['resources']['operator_inputs']['historical_default_log'] = dict(
        path='${FACTORY_MUSE_DEMO}/graph-v4/runs/fd07412594dd4491864b5fddfbf37b2f/server.log',
        how='Read-only historical E0 mixed-pack default-batch log for scheduler rehearsal; collect fresh rows for acceptance.',
        results='Original device model buffer 37396.62 MiB, KV 716 MiB, compute and host 1609.04 MiB at ubatch 512.')
    task['resources']['operator_inputs']['convert_receipt'] = dict(
        path='${FACTORY_MUSE_DEMO}/replay-r8/convert.json', how='Historical host production receipt for read-only conversion replay.')
    task['resources']['operator_inputs']['quantize_receipt'] = dict(
        path='${FACTORY_MUSE_DEMO}/replay-r8/quantize.json', how='Historical host production receipt for read-only quantization replay.')
    ingest['briefing']['how_to_fill'] = [
        'Bind the reader, source workbench and capped runner. Replay the named job with its original commit, '
        'checkpoint_manifest from checkpoint_digests, bf16, split_max_size 50G and name muse-nvfp4-v4.']
    requant['briefing']['how_to_fill'] = [
        'Bind the weight pack compiler and capped runner. Cite the trusted quantize receipt and current manifest census. '
        'Write the new recipe JSON under the owned work directory. Linked packs are read-only. '
        'Use the original producer commit, verified precision recipe and name muse-2bit-v4.']
    task['resources']['device_budget_mib'] = 110000
    for arm in ('B', 'Bub'):
        task['resources']['operator_inputs'][f'historical_prefill_{arm}'] = dict(
            path=f'${{FACTORY_MUSE_DEMO}}/lab/{arm}.stderr.log',
            how='Historical matched Q2_K E0 buffer measurement used to calibrate the estimate. Verify on the fresh mixed pack.')
    caps = task['resources']['capsules']
    task['resources']['capsules'] = [c for c in caps if c not in {
        'eval.paired_accuracy', 'analysis.expert_routing_profile', 'engine.build_expert_weight_cache'}] + ['factory.builder']
    for path, contents in [(contracts / f'{TASK}.json', contract), (tasks / f'{TASK}.json', task),
                           (tasks / f'{TASK}.plan.json', plan)]:
        path.write_text(json.dumps(contents, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    generate(Path(sys.argv[1]))
