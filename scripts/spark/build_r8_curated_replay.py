"""Build a portable native replay from the retained Muse R8 evidence, without model loads."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
import json
import re
import tempfile

from jiuwenswarm.factory import corrections, demo_board, story, taskgraph
from jiuwenswarm.factory.export import snapshot, verify
from jiuwenswarm.factory.node_finalize import digest
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService
from scripts.spark.build_demo_replays import Builder, SCHEMA, TABLES, Omitted, sha, utc
from scripts.spark.muse_replay_presentation import FACTORY, RUNTIME, RUN1_NODES, argument_diff

TASK = 'muse-2bit-demo-r8'
TITLE = 'Run 1 · Quantization + prefill (AQB)'
PRESENTER_LINES = (
    'Pin the engine, mixed-weight pack and target lab requirements.',
    'The scheduler finalizes node contracts with executable checks.',
    'JiuwenSwarm repairs the converter and verifies it on a small fixture.',
    'Connect the expert scales so the model produces valid outputs.',
    'Compile the base engine and smoke-test it on the target.',
    'Apply the mixed quantization recipe and verify the resulting weights.',
    'The verifier identifies a quantization mismatch and checks the repair.',
    'Size the prefill batch from the mixed pack’s measured memory use.',
    'Build the engine image and deliver it with the target test requirements.',
    'Compare first-token speed and answer accuracy against the measured baseline.',
)
REPO = Path(__file__).resolve().parents[2]
CONTRACT = Path('jiuwenswarm/factory/contracts') / f'{TASK}.json'
PLAN = Path('jiuwenswarm/factory/tasks') / f'{TASK}.plan.json'
IMAGE = 'da567de7ffcc4dd4bf537ee2169aa63d'


class R8Replay(Builder):
    def __init__(self, stage, graph, report, baseline, accuracy):
        super().__init__(graph.parent, stage, {})
        self.graph_home = graph
        self.report_path = report
        self.baseline_path = baseline
        self.accuracy_path = accuracy
        with tempfile.TemporaryDirectory(prefix='r8-replay-db-') as directory:
            FactoryHttpService.copy_store(graph, Path(directory))
            self.data = snapshot(Path(directory), TASK)
        self.notes = corrections.read_notes(graph / 'operator-inbox' / TASK, TASK)
        self.data['_operator_notes'] = self.notes
        self.observations = {row['obs_id']: row for row in self.data['observations']}
        self.artifact_rows = {row['artifact_id']: row for row in self.data['artifacts']}
        self.trails = corrections.project(self.data)
        self.steps = []

    def evidence(self, path, label, why, source, source_path, **extra):
        return self.key(self.copy(path, source_path, dict(source=source, **extra)), label, why)

    def key(self, path, label, why):
        self.files[path]['display_name'] = label
        return dict(path=path, label=label, why=why)

    def artifact(self, artifact_id, filename, label, why):
        row = self.artifact_rows[artifact_id]
        path = self.copy(self.graph_home / row['location'], 'evidence/graph-r8/' + filename,
                         dict(source='factory_home_artifact', source_home='graph-r8', task_id=TASK,
                              artifact_id=artifact_id, source_path=row['location']), expected=row['sha256'])
        self.artifacts.append(dict(row, exported_path=path, exported_sha256=row['sha256'], source_home='graph-r8'))
        return self.key(path, label, why)

    def projection(self, filename, value, label, why, sources):
        path = 'projections/' + filename
        self.write_json(path, value)
        data = (self.stage / path).read_bytes()
        self.files[path] = dict(source='record_projection', sources=sources, sha256=sha(data), size=len(data))
        return self.key(path, label, why)

    def obs(self, record_id):
        return self.observations[record_id]['values']

    def record(self, record_id):
        return dict(table='observations', id=record_id, source_home='graph-r8', task_id=TASK)

    def step(self, title, say, nodes, primary, files, *, refs=(), replay=None, measurement=None, notes=(), trail=None):
        if primary == TASK:
            task = self.data['tasks'][0]
            original_kind, summary, created = 'task', task['objective'], task['created']
            records = [dict(table='tasks', id=TASK, source_home='graph-r8', task_id=TASK)]
        elif isinstance(primary, dict):
            original_kind, summary, created = primary['kind'], primary['summary'], primary['created']
            records = [dict(table='file', id=primary['id'], source=primary['source'])]
            primary = primary['id']
        else:
            row = self.observations[primary]
            original_kind, created = row['kind'], row['created']
            summary = (row['values'].get('reason') or row['values'].get('rationale') or original_kind)
            records = [self.record(primary)]
        records.extend(self.record(ref) for ref in refs if ref != primary)
        records.extend(dict(table='operator-inbox', id=note['note_id'], source_home='graph-r8',
                            task_id=TASK) for note in notes)
        number = len(self.steps) + 1
        step = dict(step=number, presentation_label='Presentation title', presentation_title=title,
                    say_label='Presenter line', presenter_line=PRESENTER_LINES[number - 1], say=say,
                    graph_nodes=nodes, node_id=nodes[0],
                    original_kind=original_kind, original_summary=summary, created=created,
                    created_utc=utc(created), primary_record=primary, records=records,
                    files=[file['path'] for file in files], key_files=files)
        if replay:
            step.update(replayed_from=replay, replay_source=story.replay_origin(replay))
        if measurement:
            step['measurement'] = measurement
        if trail:
            step['correction_trail'] = trail
        self.steps.append(step)

    def build(self):
        self.contract_and_scheduler()
        self.implementation()
        self.quantization()
        self.prefill_and_image()
        self.measurements()
        self.write_bundle()

    def contract_and_scheduler(self):
        contract = self.evidence(REPO / CONTRACT, 'Owner task contract · revision 8',
                                 'Exact owner contract with the mixed pack, prefill and lab deliverables.',
                                 'repository_file', f'contracts/{TASK}.json', source_path_in_repository=str(CONTRACT))
        plan = self.evidence(REPO / PLAN, 'Original graph plan', 'Exact initial node plan and dependencies.',
                             'repository_file', f'evidence/graph-r8/{PLAN.name}', source_path_in_repository=str(PLAN))
        self.step('The contract: a 2-bit engine image for Muse Spark Open',
                  'Specify the engine artifact, target, workload and acceptance criteria. In this run: '
                  'the owner asked for an engine image from stock llama.cpp and the official NVFP4 checkpoint, '
                  'a mixed 2-bit pack and a prefill plan. The lab compared A (NVFP4) with AQB (A plus the '
                  'quantization and prefill capsules) using the delivered image.',
                  ['pin_inputs'], TASK, [contract, plan], refs=[f'{TASK}:plan:1'])
        finals = [row for row in self.observations.values() if row['kind'] == 'node_contract_final']
        refused = sum(row['kind'] == 'node_contract_refusal' for row in self.observations.values())
        row = next(row for row in finals if row['values']['node_id'] == 'size_prefill_batch')
        value = row['values']
        preliminary = demo_board.rebuild_preliminary(value['final'], value['diff'])
        if digest(preliminary) != value['preliminary_digest'] or digest(value['final']) != value['digest']:
            raise ValueError('Scheduler contract digests do not match the retained record')
        final_file = self.projection('prefill-final-contract.json', dict(preliminary=preliminary, **value),
                                     'Final contract, changes and rationale', 'Preliminary and final digests verified.',
                                     [self.record(row['obs_id'])])
        scheduler = f'sessions/{TASK}.scheduler.jsonl'
        lines = (self.graph_home / scheduler).read_bytes().splitlines(keepends=True)
        calls = {}
        retained = []
        model = None
        for number, line in enumerate(lines, 1):
            item = json.loads(line)
            if item.get('event') == 'turn.start' and item.get('node_id') == 'size_prefill_batch':
                model = item['model']
                retained.append(number)
            call = item.get('tool_call') or {}
            arguments = call.get('arguments') or {}
            if arguments.get('capability') == 'brief' and arguments.get('inputs', {}).get('node_id') == 'size_prefill_batch':
                calls[call['tool_call_id']] = number
            if item.get('tool_call_id') in calls:
                retained.extend([calls[item['tool_call_id']], number])
        if not model or len(retained) != 3:
            raise ValueError('Expected the retained scheduler model and one briefing call/result')
        briefing_path = 'evidence/graph-r8/prefill-scheduler-brief.jsonl'
        (self.stage / briefing_path).parent.mkdir(parents=True, exist_ok=True)
        excerpt = b''.join(lines[number - 1] for number in retained)
        (self.stage / briefing_path).write_bytes(excerpt)
        self.files[briefing_path] = dict(source='verbatim_excerpt', source_home='graph-r8',
                                         source_path=scheduler, source_sha256=sha(b''.join(lines)),
                                         lines=retained, sha256=sha(excerpt), size=len(excerpt))
        brief_file = self.key(briefing_path, 'Scheduler briefing and model record',
                              'Verbatim scheduler turn start and briefing request and response.')
        progress_path = 'bridge/PROGRESS.md'
        progress = (self.graph_home.parent / progress_path).read_bytes()
        line_number, refusal = next((number, line) for number, line in enumerate(progress.decode().splitlines(), 1)
                                    if 'Dry-01: pin refused scope;' in line)
        rehearsal = self.projection('scheduler-rehearsal.json', {'record': refusal},
                                    'Scheduler rehearsal: pin refused scope',
                                    'The host refused the proposal during the rehearsal before the run.',
                                    [dict(path=progress_path, line=line_number, line_sha256=sha(refusal.encode()))])
        self.step('The scheduler finalizes each node contract',
                  'Turn the planned work into executable node contracts with evidence requirements. In this run: '
                  f'the scheduler agent ({model}) read the briefing and finalized {len(finals)} node contracts. '
                  'For prefill it required a measured calibration, a cache and memory budget check, and one planned '
                  f'micro-batch per prompt. The live run recorded {refused} refusals. In rehearsal the host rejected a pin proposal for scope.',
                  ['size_prefill_batch'], row['obs_id'], [final_file, rehearsal, brief_file], refs=[r['obs_id'] for r in finals])

    def implementation(self):
        converter = 'node-check:ingest_nvfp4:converter:6:b111d738'
        wiring = 'node-check:wire_expert_scales:change:2:e9721ac4'
        e0 = 'dff1699ae04049ceb2c706cf6e7122a0'
        converter_diff = self.artifact('node-check-b111d7385af11506b28e246e-diff', 'converter.diff',
                                       'Converter code diff', 'JiuwenSwarm’s retained stacked-NVFP4 source patch.')
        converter_checks = self.projection('converter-verifier.json', self.obs(converter)['verifier'],
                                           'Factory stage · Converter verifier', 'The tiny conversion compares the packed blocks bit for bit.',
                                           [self.record(converter)])
        before = 'node-check:ingest_nvfp4:converter:2:f9ff60e9'
        trail = self.projection('converter-corrections.json', [self.observations[key] for key in [before, converter]],
                                'Converter correction sequence', 'Original advisory findings and the checked revision.',
                                [self.record(before), self.record(converter)])
        self.step('The converter: JiuwenSwarm writes it, checks pass after repairs',
                  'Convert checkpoint tensors into the engine format and verify weight values on a small fixture. In this run: '
                  'the worker extended the converter for stacked NVFP4 experts. The verifier passed bit for bit, '
                  'and the revised diff added the requested probe and scale logging.',
                  ['ingest_nvfp4'], converter, [converter_diff, converter_checks, trail], refs=[before],
                  trail=self.trails['ingest_nvfp4'])
        wiring_diff = self.artifact('node-check-e9721ac43159b081a8ae4bc6-diff', 'expert-scale-wiring.diff',
                                    'Expert scale wiring diff', 'Retained changes to expert projection scale arguments.')
        fixture = self.artifact('run-999cc53e8979-result.json', 'expert-scale-fixture.json',
                                    'Factory stage · Small-fixture verifier', 'Stock and wired KLD, slice limits and scale-free output comparison.')
        fixture_checks = {check['name']: check['detail'] for check in self.obs(wiring)['verifier']['checks']}
        kld, kld_limit = re.search(r'mean KLD ([\d.]+).*limit ([\d.]+)', fixture_checks['nvfp4_kld']).groups()
        error, tolerance = re.search(r'worst max\|d\|/max\|ref\| ([\d.]+) \(tol ([\d.]+)',
                                     fixture_checks['expert_slice']).groups()
        self.step('Expert scale wiring: stock gives NaN, wired matches',
                  'Wire quantization scales into the engine and verify numerical agreement on small fixtures. In this run: '
                  f'the fixture recorded stock NaN and wired KLD {kld} (limit {kld_limit}), with worst slice '
                  f'{error} (limit {tolerance}) and byte-identical scale-free output.',
                  ['wire_expert_scales'], wiring, [wiring_diff, fixture], refs=['156a50a3480d41f0bf02c7d43111be96'])
        build = self.artifact('run-b9a0873d31b3-result.json', 'e0-build.json', 'Factory stage · E0 compile receipt',
                              'The source commit and executable from the capped build.')
        smoke = self.artifact('run-14b78261ad4b-rows.json', 'e0-nvfp4-smoke.json',
                              'Runtime stage · E0 NVFP4 smoke · First request after start',
                              'The recorded request, generated text and timings.')
        smoke_receipt = self.artifact('run-14b78261ad4b-result.json', 'e0-nvfp4-smoke-receipt.json',
                                      'Runtime stage · Capped smoke receipt', 'Recorded 96 GiB cgroup limit and smoke outcome.')
        self.step('Base engine E0 compiled and smoke-tested',
                  'Build the pinned source and check a real-model response on the target. In this run: '
                  f"E0 compiled from the agent’s commit. One NVFP4 smoke request under the "
                  f"{self.obs(e0)['memory_max'].removesuffix('G')} GiB cap generated coherent text.",
                  ['build_base_engine'], e0, [build, smoke, smoke_receipt],
                  refs=['fcb58c0234a740e6b6c4b8d51a90d1c0', '86da5cbc27ac49079abce7c3c5129834'])

    def quantization(self):
        pack = '6b9db917eea94234955628f4dd694856'
        smoke = '4acfb90e511c48aaab800211f34e0991'
        replay_id = 'c0657386ac27465984cd23aca2053ac8'
        replay = self.obs(replay_id)['replayed_from']
        source_census = '8488b01eaf304a29be1773d5983a7a32'
        recipe = self.artifact('requant-2bit-recipe-json', 'mixed-pack-recipe.json', 'Mixed 2-bit recipe',
                               'Per-tensor target types and quantizer arguments.')
        manifest = self.artifact('run-d14d2adce4a5-pack-manifest.json', 'mixed-pack-manifest.json',
                                 'Mixed pack shard manifest', 'All 11 production shards, sizes and digests.')
        replay_result = self.obs(replay_id)['result']
        experts = replay_result['census']['routed_expert']
        source_bytes = self.obs(source_census)['manifest']['bytes']
        census = self.projection('mixed-pack-census.json', dict(census=replay_result['census'], **self.obs(pack)),
                                 'Factory stage · Mixed pack census and verifier',
                                 'Native header census, scale preservation and size.',
                                 [self.record(pack), self.record(source_census), self.record(replay_id)])
        receipt = self.artifact('run-d14d2adce4a5-result.json', 'mixed-pack-replay.json', 'Read-only replay receipt',
                                'Original job, original duration and current verification duration.')
        smoke_file = self.artifact('run-3b1a557a0045-rows.json', 'mixed-pack-smoke.json', 'Runtime stage · Eight held-out smoke rows',
                                   'Fresh mixed-pack E0 responses from the single capped run.')
        before = self.obs(source_census)['manifest']
        after_types = Counter()
        for role in replay_result['census'].values():
            after_types.update(role)
        self.step('Quantization: the new mixed 2-bit pack',
                  'Choose a bit width per weight group from a sensitivity census and build the pack. In this run: '
                  f"IQ2_XXS gate/up and Q2_K down cover {experts['iq2_xxs']} and {experts['q2_k']} routed tensors. "
                  f"The pack is {self.obs(pack)['bytes'] / 1e9:.1f} GB versus {source_bytes / 1e9:.1f} GB NVFP4. "
                  'The pack compiler produced it in v4 in '
                  f"{story.replay_duration(replay['duration_seconds'])}. R8 verified and reused it in {self.obs(pack)['replay_seconds']} s, "
                  'and eight held-out E0 prompts produced coherent text.',
                  ['requant_2bit'], pack, [recipe, census, manifest, receipt, smoke_file],
                  refs=[source_census, replay_id, smoke], replay=replay)
        self.steps[-1]['capsule_diff'] = dict(
            caption='Pack compiler · tensor types and disk size',
            before=dict(bytes=before['bytes'], tensors=before['census_by_type']),
            after=dict(bytes=self.obs(pack)['bytes'], tensors=dict(after_types),
                       recipe=self.obs(pack)['inputs'].get('target', 'IQ2_XXS gate/up, Q2_K down')))
        trail = self.trails['requant_2bit']
        note_ids = {event['source'] for event in trail['events'] if event['kind'] == 'note'}
        notes = [note for note in self.notes if note['note_id'] in note_ids or
                 ('requant' in note['text'] and '#reviewer-' in note['text'])]
        checks = [row for row in self.observations.values() if row['kind'] == 'node_check' and
                  row['values']['node_id'] == 'requant_2bit' and row['values']['state'] == 'finished']
        repairs = ['886d66f7ce25412585d92844377871b9', '3b80764e4c9b403abebbc7bf58f9f484',
                   '52511ae961ac45f0ae14a118bbc0eaf8']
        refs = [row['obs_id'] for row in checks] + repairs
        note_files = []
        for note in notes:
            name = note['note_id'] + '.json'
            relative = f'operator-inbox/{TASK}/{name}'
            note_files.append(self.evidence(self.graph_home / relative, 'Specific-fix note · ' + name[:8],
                              'Original operator-inbox record.', 'factory_home_file', 'evidence/' + relative,
                              source_home='graph-r8', source_relative_path=relative))
        note_sources = [dict(path=key['path'], sha256=self.files[key['path']]['sha256']) for key in note_files]
        sequence = self.projection('requant-corrections.json', dict(timeline=trail, checks=checks,
                                   specific_fixes=[self.observations[key] for key in repairs]),
                                   'Requant correction sequence', 'Findings, specific fixes, repairs and passing checks.',
                                   [self.record(key) for key in refs] + note_sources)
        note_index = self.projection('requant-specific-fix-notes.json', notes, 'Agent help · specific-fix notes',
                                     'Original notes citing the producer, hash convention and evidence limits.',
                                     note_sources)
        findings = [event for event in trail['events'] if event['kind'] == 'finding']
        reviewers = sum(event['actor'] == 'reviewer' for event in findings)
        host_blocked = sum(event['actor'] == 'verifier' and event['host_passed'] is False for event in findings)
        advisory_blockers = sum(event['output'] == 'pack_2bit' and event['advisory'] and
                                event['severity'] == 'blocker' and event['status'] == 'open' for event in findings)
        counts = trail['counts']
        self.step('Agent help with the verifier role',
                  'Record review findings and verify repairs against the same evidence. In this run: '
                  f'{reviewers} reviewer findings and {host_blocked} host-blocked verifier call. '
                  f"The correction trail records {counts['repairs']} repair and {counts['notes']} notes. "
                  f'{advisory_blockers} pack blockers remain advisory.',
                  ['requant_2bit'], 'node-check:requant_2bit:recipe:6:d3710718', [sequence, note_index],
                  refs=refs, notes=notes, trail=trail)

    def prefill_and_image(self):
        batch = 'baa60c2f5b274038b5fcba1e60ca240b'
        paired = '3fb85672b2a8404891c8497bcd5205d2'
        check = 'node-check:size_prefill_batch:batch_plan:2:e6929317'
        followups = ['2571ec1e2fb54defa8a349872da35e68', '2a5f37dc8236475d934f8cb0c4560f69']
        planned = self.artifact('76c2e53a2f29490baa53960a08a7abee', 'prefill-batch-plan.json',
                                'Prefill batch plan', 'Pinned batch, micro-batch, requested cache and budget.')
        verify_file = self.projection('prefill-verifier.json', dict(check=self.observations[check],
                                      paired_runtime=self.observations[paired],
                                      advisory_followups=[self.observations[key] for key in followups]),
                                      'Factory and Runtime stages · Prefill verifier and advisory follow-ups',
                                      'The capsule pass, the reviewer’s four-token tail and the paired output evidence.',
                                      [self.record(key) for key in [check, paired, *followups]])
        load_log = self.artifact('run-e5b36273f07c-server.log', 'prefill-load.log', 'Runtime stage · Planned capped load log',
                                 'Recorded buffer allocation, cache and batch settings.')
        plan = self.obs(batch)['plan']
        plan_file = json.loads((self.stage / planned['path']).read_bytes())
        reference = plan_file['reference']
        self.step('Prefill batch plan for the 2-bit engine',
                  "Size prefill batches to the target's device budget from measured costs. In this run: "
                  f"the capsule increased the micro-batch from {reference['n_ubatch']} to {plan_file['ubatch']} "
                  f"and requested {self.obs(paired)['requested_moe_cache_mib']} MiB of expert cache. "
                  f"The planned load stayed within {plan['device_budget_mib']} MiB and matched default-batch output. "
                  'The short prompt already fit in one micro-batch. The plan targeted one for the long prompt, '
                  'and the server logged 2043 + 4 tokens.',
                  ['size_prefill_batch'], check, [planned, verify_file, load_log], refs=[batch, paired, *followups],
                  trail=self.trails['size_prefill_batch'])
        self.steps[-1]['capsule_diff'] = dict(caption='Prefill arguments · default and planned settings on the mixed pack',
            before={'-b': reference['n_batch'], '-ub': reference['n_ubatch'],
                    'observed cache (MiB)': reference['device_mib']['moe_cache']},
            after={'-b': plan_file['batch'], '-ub': plan_file['ubatch'],
                   'requested cache (MiB)': plan_file['moe_cache_mib']})
        step = self.steps[-1]
        diff = argument_diff(self, 'projections/prefill-arguments.diff', step['capsule_diff']['before'],
                             step['capsule_diff']['after'], step['records'], 'Diff · Prefill arguments')
        step['files'].append(diff['path'])
        step['key_files'].append(diff)
        image_receipt = self.artifact(f'{IMAGE}:receipt', 'image-build-receipt.json', 'Image build receipt',
                                      'The accepted image id and build source commit.')
        image_check = self.artifact(f'{IMAGE}:image-check', 'image-version-check.json', 'Factory stage · Image version check',
                                    'The image ran llama-server --version without a model mount or GPU.')
        image = json.loads((self.stage / image_check['path']).read_bytes())
        self.image_id = image['image_id']
        delivery = 'labreq-2de8ad02113b333e0c22ae1f:request'
        gate = 'node-check:deliver_to_lab:lab_request:1:6f9e8d04'
        request = self.projection('lab-request-and-gate.json', [self.observations[key] for key in [delivery, gate]],
                                  'Factory stage · Lab request and delivery gate', 'The host gate’s cited image, config and pack digests.',
                                  [self.record(delivery), self.record(gate)])
        rejected = [obs for obs in self.observations.values() if obs['kind'] == 'build_image_request_validation']
        failed = self.observations['107c03b2666d44ac9e6572812a57e360:build-result']
        blocker = next(obs for obs in self.observations.values() if obs['kind'] == 'build_image_recipe_blocker'
                       and obs['values']['build_attempt_id'] == failed['obs_id'].split(':')[0])
        checker_files = [
            self.projection(f"checker-{obs['obs_id'][:8]}.json", obs, label, why, [self.record(obs['obs_id'])])
            for obs, label, why in [
                *((obs, 'Rejected build request · ' + obs['values']['diagnostics'][0]['message'],
                   'Host validation stopped the request before a build started.') for obs in rejected),
                (failed, 'Failed image build 107c03b2', 'Build result before the recipe repair.'),
                (blocker, 'Image build failure and recipe repair', 'The recorded asset failure and approved CMake flags.')]]
        self.step('The image and the gate',
                  'Package the engine, verify its executable without a model, and seal the target request. In this run: '
                  f'the host rejected {len(rejected)} malformed build requests. A later build failed while fetching UI assets. '
                  f"After the recipe repair, commit {image['source_commit'][:9]} built image {image['image_id'][7:19]}. "
                  'The image passed --version and the delivery gate checked the retained digests.',
                  ['build_image', 'deliver_to_lab'], delivery, [image_receipt, image_check, request, *checker_files],
                  refs=[*(obs['obs_id'] for obs in rejected), failed['obs_id'], blocker['obs_id'], f'{IMAGE}:build-result', gate])

    def measurements(self):
        report = json.loads(self.report_path.read_bytes())
        if report.get('format') == 'r8-final-bench':
            cells = report['cells']
            by_cell = {(cell['arm'], cell['request'], cell['state']): cell for cell in cells}
            expected = {(arm, request, state) for arm in ('A', 'AQB') for request in ('p512', 'p2048')
                        for state in ('cold', 'warm')}
            if by_cell.keys() != expected or len(cells) != len(expected):
                raise ValueError('Expected exactly one measured A and AQB row per prompt length and cold/warm state')
            if any(cell['generated_tokens'] != 32 for cell in cells):
                raise ValueError('The final benchmark requires 32 generated tokens in every speed cell')
            report_file = self.evidence(self.report_path, 'Runtime stage · Final engine benchmark', 'Measured A and AQB speed and accuracy.',
                                        'lab_file', 'evidence/lab/report.json', source_relative_path='r8-final/report.json')
            look = report['accuracy']
            measurement = dict(baseline='A · NVFP4 baseline. AQB · mixed 2-bit + prefill plan. Warm server rows show medians',
                rows=[dict(cell, path=report_file['path'], pointer=f'/cells/{index}', status='accepted', reasons=[])
                      for index, cell in enumerate(cells)],
                accuracy=dict(n=look['n'], path=report_file['path'], reference_pct=round(100*look['acc_ref'],1),
                              candidate_pct=round(100*look['acc_cand'],1), loss_pts=look['loss_pts'],
                              lo_pts=look['lo_pts'], hi_pts=look['hi_pts']))
            primary = dict(kind=report['format'],
                           summary='The delivered image ran both speed arms. MMLU zero-shot paired the retained NVFP4 answers '
                                   'with the mixed-pack load.',
                           created=datetime.fromisoformat(report['ended_utc']).timestamp(),
                           id=report_file['path'], source='r8-final/report.json')
            warm_a_512 = by_cell['A', 'p512', 'warm']['ttft_ms'] / 1000
            warm_aqb_512 = by_cell['AQB', 'p512', 'warm']['ttft_ms'] / 1000
            warm_a_2048 = by_cell['A', 'p2048', 'warm']['ttft_ms'] / 1000
            warm_aqb_2048 = by_cell['AQB', 'p2048', 'warm']['ttft_ms'] / 1000
            self.step('Measured speed and accuracy',
                      'Measure engine speed and correctness on the target with matched workloads. In this run: '
                      f'for Warm server rows, AQB reached the first token in {warm_aqb_512:.1f} s versus {warm_a_512:.1f} s for A '
                      f'at 512, and {warm_aqb_2048:.1f} s versus {warm_a_2048:.1f} s at 2048. '
                      f"On {look['n']} MMLU zero-shot questions, A scored {look['acc_ref']:.1%} and AQB scored {look['acc_cand']:.1%}.",
                      ['deliver_to_lab'], primary, [report_file], measurement=measurement)
            self.steps[-1]['presenter_line'] = (
                f'AQB reached its first token in {warm_aqb_2048:.1f} s versus {warm_a_2048:.1f} s for A '
                'at 2,048 tokens on a warm server.')
            return
        historical = json.loads(self.baseline_path.read_bytes())
        if sha(self.baseline_path.read_bytes()) != report['baseline']['sha256']:
            raise ValueError('Historical baseline digest differs from the report’s baseline pin')
        accuracy = json.loads(self.accuracy_path.read_bytes())
        look = next(look for look in accuracy['outputs']['looks'] if look['decision'] == 'pass')
        report_file = self.evidence(self.report_path, 'Final lab report', 'Corrected revised-rule measurements and sample evidence.',
                                    'lab_file', 'evidence/lab/report.json', source_relative_path='r8-final/report.json')
        baseline_file = self.evidence(self.baseline_path, 'Nov 25 baseline A source', 'Historical E0 on NVFP4, Q2_K-era lab.',
                                      'lab_file', 'evidence/lab/baseline-a-source.json', source_relative_path='lab/report-abcde.json')
        accuracy_file = self.evidence(self.accuracy_path, 'Q2_K paired MMLU verifier', 'Historical paired look at 250 questions.',
                                      'lab_file', 'evidence/lab/q2-k-paired-mmlu.json', source_relative_path='acc/verify-out.json')
        raw_rows = report['rows']
        cells = {(row['arm'], row['request'], row['state']) for row in raw_rows}
        if cells != {(arm, request, state) for arm in 'BP' for request in ('p512', 'p2048')
                     for state in ('cold', 'warm')} or len(raw_rows) != 8:
            raise ValueError('Expected one recorded row for each B/P × length × state cell')
        if any(not row.get('corrected_verdict') for row in raw_rows):
            raise ValueError('The replay requires post-run quiet-rule decisions for all eight cells')

        def rows(document, key, arm=None):
            result = []
            for index, row in enumerate(document['rows']):
                if arm and row['arm'] != arm:
                    continue
                quiet = row.get('quiet') or {}
                result.append(dict(arm=row['arm'], request=row['request'], state=row['state'],
                                   repeat=row.get('repeat'), generated_tokens=row.get('generated_tokens'),
                                   prompt_tokens=row['prompt_tokens'], ttft_ms=row['client_ttft_ms'],
                                   decode_tps=row['decode_tokens_per_second'], total_ms=row['request_total_ms'],
                                   prefill_tps=row['prompt_tokens_per_second'],
                                   status=quiet.get('status') or 'historical', reasons=quiet.get('reasons') or [],
                                   launch_verdict=row.get('launch_verdict'), corrected_verdict=row.get('corrected_verdict'),
                                   path=key['path'], pointer=f'/rows/{index}'))
            return result

        measurement = dict(rows=rows(historical, baseline_file, arm='A') + rows(report, report_file),
                           baseline='A · Nov 25, E0 on NVFP4, Q2_K-era lab',
                           accuracy=dict(loss_pts=look['loss_pts'], lo_pts=look['lo_pts'], hi_pts=look['hi_pts'],
                                         n=look['n'], path=accuracy_file['path']))
        row_projection = self.projection('lab-measurement-rows.json', measurement, 'Per-request measurements',
                                         'Individual TTFT, decode and total values, with source pointers.',
                                         [dict(path=key['path'], sha256=self.files[key['path']]['sha256'])
                                          for key in [report_file, baseline_file, accuracy_file]])
        last = max(sample['utc'] for row in raw_rows for sample in row['quiet']['samples'])
        primary = dict(kind=report['format'], summary='The revised-rule R8 lab timed B and P from the delivered image.',
                       created=datetime.fromisoformat(last).timestamp(), id=report_file['path'] + '#/rows',
                       source='r8-final/report.json')
        accepted = {
            (cell['arm'], cell['request'], cell['state']): cell
            for cell in report['comparison']['cells']
        }
        warm_b = accepted['B', 'p2048', 'warm']['measured']['client_ttft_ms']
        warm_p = accepted['P', 'p2048', 'warm']
        warm_a = warm_p['baseline_a']['client_ttft_ms']
        warm_p = warm_p['measured']['client_ttft_ms']
        self.step('The measured result',
                  'Measure speed on the target with matched workloads. In this run: '
                  f'at 2048 tokens on a Warm server, TTFT was {warm_a / 1000:.1f} s for historical A, {warm_b / 1000:.1f} s for B '
                  f'and {warm_p / 1000:.1f} s for P. P was {warm_a / warm_p:.1f}× as fast to the first token as A.',
                  ['deliver_to_lab'], primary, [row_projection, report_file, baseline_file, accuracy_file],
                  measurement=measurement)

    def write_bundle(self):
        graph = taskgraph.from_records(self.data)
        node_ids = {node['node_id'] for node in graph['nodes']}
        if any(node not in node_ids for step in self.steps for node in step['graph_nodes']):
            raise ValueError('Replay references a node missing from the recorded R8 graph')
        done = sum(node['state'] == 'done' for node in graph['nodes'])
        outcome = f"{done} of {len(graph['nodes'])} nodes complete · AQB engine image delivered · Lab measured"
        stages = [(), (), (FACTORY,), (FACTORY,), (FACTORY, RUNTIME), (FACTORY, RUNTIME),
                  (FACTORY,), (FACTORY, RUNTIME), (FACTORY,), (RUNTIME,)]
        for step, where in zip(self.steps, stages, strict=True):
            step['stages'] = where
        self.write_json('replay.json', dict(schema=SCHEMA, title=TITLE, order=1, graph_mode='recorded',
                        summary='Ten steps from the owner contract to the delivered image and its lab measurements.',
                        primary_task=TASK, source_homes=['graph-r8'], node_presentation=RUN1_NODES, steps=self.steps,
                        presentation_header=dict(
                            objective='Build a mixed 2-bit Muse engine, size its prefill batch and benchmark it on Spark.',
                            outcome=outcome,
                            image_id=self.image_id),
                        contract_versions=[dict(version=8, path=f'contracts/{TASK}.json',
                                                sha256=self.files[f'contracts/{TASK}.json']['sha256'])]))
        for table in ('tasks', *TABLES):
            values = self.data[table] if table != 'artifacts' else [
                self.artifact_rows[row['artifact_id']] for row in self.artifacts]
            self.write_json(f'records/{table}.json', values)
        self.write_json('artifacts.json', self.artifacts)
        self.write_json('key_files.json', {str(step['step']): step['key_files'] for step in self.steps})
        self.write_json('provenance.json', dict(files=self.files, source_homes=['graph-r8'],
                        records={str(step['step']): step['records'] for step in self.steps}))


def build(graph, report, baseline, accuracy, out, lab_report_root=None):
    out = out.resolve()
    if out.exists() or out.is_relative_to(graph.resolve()):
        raise ValueError('Output must be a new directory outside the factory graph')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.r8-replay-', dir=out.parent) as directory:
        stage = Path(directory) / 'bundle'
        stage.mkdir()
        try:
            replay = R8Replay(stage, graph.resolve(), report, baseline, accuracy)
            replay.build()
        except Omitted as exc:
            raise ValueError(f'Required evidence matched the export secret scanner: {exc}') from exc
        if lab_report_root:
            from scripts.spark.build_muse_lab_reports import write_lab_report
            write_lab_report(stage, lab_report_root, 1)
        replay.write_json('MANIFEST.json', {path.relative_to(replay.stage).as_posix(): sha(path.read_bytes())
                        for path in sorted(replay.stage.rglob('*')) if path.is_file()})
        verify(stage)
        stage.rename(out)
    return out


def main(argv=None):
    muse = Path.home() / 'muse-demo'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph', type=Path, default=muse / 'graph-r8')
    parser.add_argument('--report', type=Path, default=muse / 'r8-final/report.json')
    parser.add_argument('--baseline', type=Path, default=muse / 'lab/report-abcde.json')
    parser.add_argument('--accuracy', type=Path, default=muse / 'acc/verify-out.json')
    parser.add_argument('--out', type=Path, default=muse / 'r8-final/curated-replay')
    parser.add_argument('--lab-report-root', type=Path, help='Muse workspace containing retained lab report sources')
    args = parser.parse_args(argv)
    print(build(args.graph, args.report, args.baseline, args.accuracy, args.out, args.lab_report_root))


if __name__ == '__main__':
    main()
