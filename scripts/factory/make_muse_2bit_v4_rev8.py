"""Revision 8 of contract muse-2bit-ttft-v4: the graph ends at a built engine image (owner, 2026-11-26).

Called by make_muse_2bit_v4.py on the revision 7 contract. Decisions of the contract owner (2026-11-26):

1. The one CC after the quantization is the prefill batch sizing (engine.size_prefill_batch): the largest measured
   lever after the quantization (Nov 25, by hand: warm 2048-token TTFT 287 -> 114 s). It runs in the graph as a
   configuration step: a plan from a load log and one capped load that confirms it. Timing stays in the lab.
2. The seeded expert cache port (port_ttft_cache) and the E1 build (build_candidate) leave the graph. The routing
   profile (record_profile, done) is kept and shipped with the image for later work; no arm uses it.
3. A new node build_image compiles the owned checkout into an engine image (factory.builder, Docker) and records the
   run configuration the lab uses. No model is loaded inside an image in the graph.
4. The lab runs once, after delivery: arms B (the 2-bit pack on the image) and P (B plus the batch plan). Arm A is
   the baseline measured on Nov 25 (E0 on NVFP4) and is not rerun. Accuracy of the 2-bit pack is not tested: the
   paired MMLU result of the Q2_K pack (Nov 25) is shown as indicative.
5. Reviewer findings are advisory on the new nodes: the capsule verifier and the host checks decide.

Each node the scheduler still has to finalize carries a `briefing`: why the node exists, measured facts with their
source, pitfalls found in earlier runs and how to fill its slots. The scheduler reads it with the task and plan.
"""
from __future__ import annotations

ADVISORY = 'advisory'
BIND = {'id': 'bind', 'at': 'work.bound_ccs', 'kind': 'ccs',
        'from': 'The capsule catalog and the capsule docs in the brief, what the upstream nodes were built with and '
                'what failed before for this node.'}
EFFECTS = ['process.exec', 'workspace.read', 'workspace.write']


def _top_level(contract):
    contract['version'] = 8
    contract['title'] = ('Muse Spark Open on DGX Spark: a mixed 2-bit pack (IQ2_XXS and Q2_K) and a prefill batch plan, '
                         'built into an engine image')
    contract['purpose'] = (
        'Starting from stock llama.cpp and the official Muse Spark Open NVFP4 checkpoint, build an engine image that '
        'runs a mixed 2-bit requantization of the model (IQ2_XXS for the routed gate and up projections, Q2_K for '
        'down) with a prefill batch sized so a 2048-token prompt streams the experts once. The factory graph does the '
        'implementation: the converter and expert scale wiring the checkpoint needs, the base engine, the 2-bit pack, '
        'the batch plan, the image. The lab then measures once how much time to first token, decode rate and total '
        'request time change against the NVFP4 baseline.')
    contract['scope'] = {
        'covers': [
            'the NVFP4 GGUF pack built from the official checkpoint, with the converter and expert scale wiring stock '
            'llama.cpp 9048bad8 needs for it',
            'a mixed 2-bit requantization of that pack (IQ2_XXS gate and up, Q2_K down, other tensors unchanged)',
            'the server prefill batch, micro-batch and MoE cache size chosen by engine.size_prefill_batch',
            'an engine image (Docker, sm_121) built from the owned checkout, and the run configuration for the lab',
            'in the lab, once: client time to first token, decode tokens per second and total request time at 512 and '
            '2048 rendered prompt tokens, cold and warm, for arms B and P against baseline A (Nov 25)',
        ],
        'excludes': [
            'an accuracy test of the 2-bit pack (the Q2_K paired MMLU result of Nov 25 is shown as indicative only)',
            'the seeded expert cache and other expert caching changes',
            'image, audio and video inputs',
            'throughput under concurrent requests',
            'hardware other than one DGX Spark',
        ],
    }
    contract['arms'] = [
        {'id': 'A', 'role': 'baseline',
         'summary': 'Base engine E0 (stock plus expert scale wiring) on the NVFP4 pack. Measured on Nov 25 and not '
                    'rerun: the lab reuses that result.',
         'deviations': ['Expert scale wiring, needed for stock to run the official NVFP4 weights correctly',
                        '--moe-cache-mib 61440 under the 110000 MiB device budget (its NVFP4 compute buffer of about '
                        '8 GiB leaves no more)']},
        {'id': 'B', 'role': 'candidate', 'from': 'A',
         'summary': 'The engine image on the mixed 2-bit pack at the default batch: the quantization change alone.',
         'deviations': ['Routed experts IQ2_XXS for the gate and up projections, Q2_K for down, instead of NVFP4',
                        '--moe-cache-mib from the size_prefill_batch plan (device budget filled)']},
        {'id': 'P', 'role': 'combined', 'from': 'B',
         'summary': 'Arm B plus the planned prefill batch (-b and -ub from the batch plan), so a 2048-token prompt is '
                    'prefilled in one micro-batch.',
         'deviations': ['Routed experts IQ2_XXS for the gate and up projections, Q2_K for down, instead of NVFP4',
                        'Server batch and micro-batch from the size_prefill_batch plan',
                        '--moe-cache-mib from the size_prefill_batch plan (device budget filled)']},
    ]
    checks = {c['id']: c for c in contract['correctness']['checks']}
    for gone in ('gate_unset_parity', 'gate_set_activation', 'accuracy_2bit'):
        checks.pop(gone)
    checks['pack_2bit_census']['applies_to'] = ['B', 'P']
    checks['prefill_batch_applied'].update(
        does='The arm P server prints the planned n_batch and n_ubatch, its device buffers fit the plan budget, and '
             'its greedy outputs agree with arm B (byte-identical or a common prefix of at least 64 characters, since '
             'a different micro-batch split changes the float summation order).',
        applies_to=['P'])
    checks['image_starts'] = {
        'id': 'image_starts',
        'does': 'The engine image starts its llama-server without a model (--version) and reports the build of the '
                'owned checkout commit; its binary digest equals the build record.',
        'applies_to': ['B', 'P']}
    contract['correctness']['checks'] = list(checks.values())
    contract['acceptance']['rules'] = [
        'A timed cell counts only when the machine is quiet: load below 1.0 and no builds running.',
        'B and P differ from A in their weights, so their outputs are not expected to match A; correctness for B and '
        'P is the pack census, the image check, coherent text, and for P agreement with B.',
        'Speed is reported as change against A (Nov 25), per prompt size, cold and warm separately.',
        'Accuracy of the 2-bit pack is not claimed; the Q2_K paired MMLU result is labelled indicative.',
        'Failures and no-gain results are reported, not dropped.',
    ]
    protocol = contract['measurement']['protocol']
    protocol['notes'] = ('One server load per arm (B then P) from the engine image under the memory cap. Per prompt size: '
                         'one cold request (pack pages evicted with posix_fadvise DONTNEED before it, reported '
                         'separately) then one warm request, 32 generated tokens each. Arm A is the Nov 25 result.')


def _size_prefill_batch(r6_like):
    node = r6_like
    node.update(
        objective='Size the server prefill batch so each lab prompt is prefilled in one micro-batch if the device '
                  'budget allows, give the rest of the budget to the MoE expert cache, and confirm the plan on one '
                  'capped load of E0 with the 2-bit pack. This is configuration, not timing: the lab times it.',
        requirement_ids=['P', 'prefill_batch_applied', 'cold_smoke'],
        predecessors=['build_base_engine', 'requant_2bit'],
        inputs=[{'name': 'base_engine', 'from': 'build_base_engine.base_engine'},
                {'name': 'pack_2bit', 'from': 'requant_2bit.pack_2bit'},
                {'name': 'prompt_512', 'from': 'contract:prompt_512'},
                {'name': 'prompt_2048', 'from': 'contract:prompt_2048'}],
        outputs=[{'name': 'batch_plan', 'kind': 'evidence', 'criteria': [
            'A factory.prefill-batch-plan/1 from a -lv 4 load log of E0 on the 2-bit pack at the default batch: the '
            'batch and micro-batch sizes, the device estimate against the budget, and micro-batches per lab prompt '
            'before and after.',
            'One capped load of E0 on the 2-bit pack with the planned arguments: the server applied them, its device '
            'buffers fit the budget, and greedy outputs of the lab requests agree with the default batch '
            '(byte-identical or a long common prefix).',
            'The plan sizes the MoE cache (--moe-cache-mib in its args) and the capped load with the planned arguments '
            'uses the device budget to within headroom plus 2 GiB; if the linear compute estimate left more, the plan '
            'is redone from that load\'s log and loaded again.']}],
        node_limits={'turns': 20, 'gpu_launches': 3, 'time_s': 3600},
        authority_ceiling={'effects': EFFECTS, 'workspace': 'read'},
        work={'helpful_ccs': ['engine.size_prefill_batch', 'factory.capped_runner'],
              'capability': 'engine.size_prefill_batch.verify',
              'eligible_ccs': ['engine.size_prefill_batch', 'factory.capped_runner']},
        verifiers=[{'output': 'batch_plan', 'verifier': 'engine.size_prefill_batch.verify',
                    'stage': 'runtime acceptance', 'review': ADVISORY,
                    'inputs': {'device_budget_mib': 110000, 'prompt_tokens': [511, 2047], 'min_agree_chars': 64,
                               'fill_moe_cache_headroom_mib': 2048}}],
        hands_to='build_image', stage='preliminary',
        slots=[BIND, {'id': 'batch_choice', 'at': 'outputs.batch_plan.criteria', 'kind': 'criteria',
                      'from': 'The compute and KV buffers in the default-batch load log and the free memory now: one '
                              'criterion naming the micro-batch sizes to try, in order.'}],
        bounds={'verifiers.batch_plan.inputs.device_budget_mib': 'lower',
                'verifiers.batch_plan.inputs.min_agree_chars': 'higher',
                'verifiers.batch_plan.inputs.fill_moe_cache_headroom_mib': 'lower'},
        briefing={
            'summary': 'The one CC after the quantization. Prefill on the GB10 streams every routed expert once per '
                       'micro-batch, so fewer micro-batches per prompt means less streaming and a shorter time to '
                       'first token. The plan must leave the expert cache as large as the budget allows, or decode '
                       'gets slower.',
            'facts': [
                'Nov 25 lab, by hand (Q2_K pack): -b 2048 -ub 2048 cut warm 2048-token TTFT from 287 s to 114 s; '
                'decode unchanged at about 0.85 tok/s (report-abcde.json, arms C and D).',
                'The lab prompts render to 511 and 2047 tokens, so -ub 2048 prefills either in one micro-batch.',
                'Device budget 110000 MiB (128 GiB less 14 GiB). On the GB10 device memory is system memory and is '
                'not charged to the cgroup: factory.capped_runner adds -fitt so the llama.cpp fit stays in budget.',
                'Q2_K, Nov 25 -lv 4 logs: model 37397 MiB on device, KV 716 MiB; compute buffer 1539 MiB at the '
                'default batch, 2128 MiB at -ub 2048. The 2-bit pack on E0 (Nov 26): compute 1.5 GiB at the default '
                'batch, load 164 s.',
                'engine.size_prefill_batch 1.2.0: fill_moe_cache_headroom_mib gives the rest of the budget to '
                '--moe-cache-mib after the planned compute and KV buffers.',
            ],
            'pitfalls': [
                'An agent sweep (Nov 25) took -ub 4096 with a smaller 48 GiB cache: decode fell to 0.55-0.61 tok/s. '
                'Larger micro-batches than the prompt need buy nothing here and cost cache.',
                'The SWA KV buffer grows with the micro-batch (460 MiB at the default, 1104 MiB at 4096): read it from '
                'the log, do not assume it is fixed.',
                'Each load takes about 3 minutes and needs the machine gate (100 GiB available, no other GPU job); '
                'a MEMORY_LOW stop is a host fault to report, not a plan failure.',
            ],
            'how_to_fill': [
                'batch_choice: try 2048 first (one micro-batch per lab prompt); name a smaller fallback only if the '
                'default-batch log shows 2048 does not fit the budget with a cache at least as large as arm B gets.',
                'bind: engine.size_prefill_batch for the plan and verify, factory.capped_runner for the two loads.',
            ]},
    )
    return node


def _build_image():
    return {
        'node_id': 'build_image', 'kind': 'build',
        'objective': 'Compile the owned checkout (stock 9048bad8 plus the converter and the expert scale wiring) into '
                     'an engine image for the Spark with factory.builder, check that the image starts, and record '
                     'the run configuration the lab uses: the image, the 2-bit pack and its manifest, and the batch '
                     'plan arguments.',
        'requirement_ids': ['B', 'P', 'image_starts'],
        'predecessors': ['wire_expert_scales', 'build_base_engine', 'requant_2bit', 'size_prefill_batch'],
        'inputs': [{'name': 'change', 'from': 'wire_expert_scales.change'},
                   {'name': 'base_engine', 'from': 'build_base_engine.base_engine'},
                   {'name': 'pack_2bit', 'from': 'requant_2bit.pack_2bit'},
                   {'name': 'batch_plan', 'from': 'size_prefill_batch.batch_plan'}],
        'outputs': [
            {'name': 'image', 'kind': 'image', 'criteria': [
                'One factory.builder build (target spark-gb10, build_target llama-server, delivery image) of the owned '
                'checkout at the commit E0 was built from; its build receipt names the image.']},
            {'name': 'image_check', 'kind': 'evidence', 'criteria': [
                'The image runs llama-server --version with no network and no model, and the reported build matches '
                'the owned checkout commit; the binary digest in the build record is cited.',
                'No model is loaded in this node.']},
            {'name': 'run_config', 'kind': 'evidence', 'criteria': [
                'One JSON evidence record for the lab: image id and tag, the 2-bit pack path and the digest of its '
                'manifest, the device budget arguments, and for arm P the batch plan\'s -b, -ub and --moe-cache-mib '
                '(arm B: the plan\'s --moe-cache-mib at the default batch).']}],
        'evidence_obligations': ['captured_input_and_output', 'invocation_observation'],
        'node_limits': {'turns': 15, 'build_attempts': 3, 'gpu_launches': 0, 'time_s': 7200},
        'authority_ceiling': {'effects': EFFECTS, 'workspace': 'read'},
        'work': {'helpful_ccs': ['factory.builder', 'factory.capped_runner'],
                 'eligible_ccs': ['factory.builder', 'factory.capped_runner', 'factory.lab_manager']},
        'verifiers': [{'output': 'image'},
                      {'output': 'image_check', 'review': ADVISORY},
                      {'output': 'run_config', 'review': ADVISORY}],
        'hands_to': 'deliver_to_lab', 'stage': 'preliminary', 'slots': [BIND],
        'briefing': {
            'summary': 'The end of the implementation: the code the graph changed becomes an engine image the lab can '
                       'run. Nothing is measured here.',
            'facts': [
                'The owned checkout llama.cpp-muse is at cd8937e4f: stock 9048bad8, then 6eeca78bd (converter) and '
                'cd8937e4f (expert scale wiring). E0 was built natively from it on Nov 26 in about 4 minutes and '
                'passed the NVFP4 smoke.',
                'factory.builder with target spark-gb10 and build_target llama-server compiles with the sm_121 flags '
                'and packages /opt/llamacpp/llama-server on the cached runtime base image (docker build '
                '--network=none --pull=false), then tags it factory/llamacpp:artifact-<id>.',
                'Pack manifests (factory.pack-manifest/1) sit beside each pack as <stem>.manifest.json; the capped '
                'runner manifest recipe hashes a pack without loading it.',
            ],
            'pitfalls': [
                'For spark-gb10 the builder requires a clean `dependency` {path, commit} even for llama-server, whose '
                'flags ignore it: pass the owned checkout and the same commit.',
                'The source must be clean with HEAD equal to the commit; the tag must be factory/llamacpp:<name>; the '
                'Spark build deadline is at most 5400 s.',
                'Do not load the model in the image here: Docker containers are not under the capped runner\'s '
                'cgroup. Model loads from the image are the lab\'s, with a container memory cap.',
            ],
            'how_to_fill': [
                'bind: factory.builder for the image build; factory.capped_runner only if a pack manifest is missing '
                'and must be hashed (manifest recipe, no model load).',
            ]},
    }


def _deliver(node):
    node.update(
        objective='The gate: ship the image once, with its run configuration, both pack manifests and the routing '
                  'profile, and the lab task for arms B and P, to the lab manager. Delivery is refused unless every '
                  'upstream check passed and the shipped digests match the recorded ones.',
        requirement_ids=['B', 'P', 'server_token_count', 'prefill_batch_applied', 'image_starts', 'client_ttft_ms',
                         'decode_tokens_per_second', 'request_total_ms', 'prompt_tokens_per_second',
                         'sampled_peak_memory_bytes', 'load_seconds', 'cold_smoke'],
        predecessors=['build_image', 'build_base_engine', 'record_profile'],
        inputs=[{'name': 'image', 'from': 'build_image.image'},
                {'name': 'run_config', 'from': 'build_image.run_config'},
                {'name': 'sources', 'from': 'build_base_engine.base_engine'},
                {'name': 'profile', 'from': 'record_profile.profile'}],
        outputs=[{'name': 'lab_request', 'kind': 'lab_request', 'criteria': [
            'The lab task fills arms B and P with the shipped image and run configuration and runs every check and '
            'metric, cold and warm, at 512 and 2048 tokens. Arm A is the Nov 25 baseline result, cited, not rerun. '
            'No accuracy test: the Q2_K paired MMLU result is cited as indicative.']}],
        node_limits={'turns': 10},
        work={'helpful_ccs': ['factory.lab_manager'], 'eligible_ccs': ['factory.lab_manager']},
        verifiers=[{'output': 'lab_request'}],
        slots=[BIND], stage='preliminary',
        briefing={
            'summary': 'The last node of the graph and the release gate. After it the lab runs once.',
            'facts': [
                'Baseline A (Nov 25, E0 on NVFP4, warm): TTFT 201.6 s at 512 and 606.7 s at 2048 tokens; decode 0.326 '
                'tok/s; total 996.8 s at 2048 (report-abcde.json).',
                'Indicative accuracy (Q2_K pack, Nov 25): paired MMLU zero-shot at 250 questions, loss +0.8 points, '
                'interval [-2.9, +4.7], pass at margin 5.',
            ],
            'pitfalls': ['A mismatched pack or image digest must block delivery; do not ship a pack without its manifest.'],
            'how_to_fill': ['bind: factory.lab_manager.'],
        },
    )
    node.pop('bounds', None)
    return node


def revise_to_8(contract):
    import copy
    _top_level(contract)
    NODES = contract['extensions']['factory.node-contracts']['nodes']
    by_id = {n['node_id']: n for n in NODES}
    # Rev 7 removed size_prefill_batch; rev 8 brings it back on E0 (no E1 in this graph).
    spb = _size_prefill_batch({'node_id': 'size_prefill_batch', 'kind': 'tune',
                               'evidence_obligations': ['captured_input_and_output', 'invocation_observation',
                                                        'mandatory_checks']})
    keep = [n for n in NODES if n['node_id'] not in {'port_ttft_cache', 'build_candidate', 'deliver_to_lab'}]
    by_id['record_profile']['requirement_ids'] = ['B']
    by_id['record_profile']['hands_to'] = 'deliver_to_lab'
    by_id['requant_2bit']['requirement_ids'] = ['B', 'pack_2bit_census', 'cold_smoke']
    deliver = _deliver(copy.deepcopy(by_id['deliver_to_lab']))
    NODES[:] = keep + [spb, _build_image(), deliver]
    for node in NODES:
        if node['node_id'] == 'requant_2bit':
            node['hands_to'] = 'size_prefill_batch'
        node.setdefault('authority_ceiling', {})
    contract['provenance']['notes'].append(
        'Revision 8 (owner, 2026-11-26): the graph ends at a built engine image. Kept: pin_inputs, ingest_nvfp4, '
        'wire_expert_scales, build_base_engine, requant_2bit and record_profile (done in the Nov 26 run). Back: '
        'size_prefill_batch on E0 and the 2-bit pack (configuration, confirmed on one capped load). New: build_image '
        '(factory.builder Docker image, image check without a model, run configuration). Removed: port_ttft_cache, '
        'build_candidate. deliver_to_lab is the gate and ships arms B and P; arm A is the Nov 25 result; no accuracy '
        'test (Q2_K result indicative). Reviewer findings advisory on the new nodes. Nodes to finalize carry a '
        'briefing for the scheduler.')
    return contract
