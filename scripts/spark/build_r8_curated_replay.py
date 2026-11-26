"""Build a portable native replay from the retained Muse R8 evidence, without model loads."""
from __future__ import annotations

import argparse
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

TASK = 'muse-2bit-demo-r8'
TITLE = 'Muse R8 · Contract to measured engine'
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
                    say_label='Presenter line', say=say, graph_nodes=nodes, node_id=nodes[0],
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
                  'The owner asked for an engine image from stock llama.cpp and the official NVFP4 checkpoint, '
                  'a mixed 2-bit pack and a prefill plan, with the lab measuring the delivered image.',
                  ['pin_inputs'], TASK, [contract, plan], refs=[f'{TASK}:plan:1'])
        finals = [row for row in self.observations.values() if row['kind'] == 'node_contract_final']
        refused = sum(row['kind'] == 'node_contract_refusal' for row in self.observations.values())
        row = next(row for row in finals if row['values']['node_id'] == 'requant_2bit')
        value = row['values']
        preliminary = demo_board.rebuild_preliminary(value['final'], value['diff'])
        if digest(preliminary) != value['preliminary_digest'] or digest(value['final']) != value['digest']:
            raise ValueError('Scheduler contract digests do not match the retained record')
        final_file = self.projection('requant-final-contract.json', dict(preliminary=preliminary, **value),
                                     'Final contract, changes and rationale', 'Preliminary and final digests verified.',
                                     [self.record(row['obs_id'])])
        scheduler = f'sessions/{TASK}.scheduler.jsonl'
        lines = (self.graph_home / scheduler).read_bytes().splitlines(keepends=True)
        calls = {}
        retained = []
        model = None
        for number, line in enumerate(lines, 1):
            item = json.loads(line)
            if item.get('event') == 'turn.start' and item.get('node_id') == 'requant_2bit':
                model = item['model']
                retained.append(number)
            call = item.get('tool_call') or {}
            arguments = call.get('arguments') or {}
            if arguments.get('capability') == 'brief' and arguments.get('inputs', {}).get('node_id') == 'requant_2bit':
                calls[call['tool_call_id']] = number
            if item.get('tool_call_id') in calls:
                retained.extend([calls[item['tool_call_id']], number])
        if not model or len(retained) != 3:
            raise ValueError('Expected the retained scheduler model and one briefing call/result')
        briefing_path = 'evidence/graph-r8/requant-scheduler-brief.jsonl'
        (self.stage / briefing_path).parent.mkdir(parents=True, exist_ok=True)
        excerpt = b''.join(lines[number - 1] for number in retained)
        (self.stage / briefing_path).write_bytes(excerpt)
        self.files[briefing_path] = dict(source='verbatim_excerpt', source_home='graph-r8',
                                         source_path=scheduler, source_sha256=sha(b''.join(lines)),
                                         lines=retained, sha256=sha(excerpt), size=len(excerpt))
        brief_file = self.key(briefing_path, 'Scheduler briefing and model record',
                              'Verbatim scheduler turn start and briefing request and response.')
        self.step('The scheduler finalizes each node contract',
                  f'The scheduler agent ({model}) read the briefing and finalized {len(finals)} node contracts, '
                  f'with {refused} refusals. The requant contract gives the records behind its input bindings and rationale.',
                  ['requant_2bit'], row['obs_id'], [final_file, brief_file], refs=[r['obs_id'] for r in finals])

    def implementation(self):
        converter = 'node-check:ingest_nvfp4:converter:6:b111d738'
        wiring = 'node-check:wire_expert_scales:change:2:e9721ac4'
        e0 = 'dff1699ae04049ceb2c706cf6e7122a0'
        converter_diff = self.artifact('node-check-b111d7385af11506b28e246e-diff', 'converter.diff',
                                       'Converter code diff', 'JiuwenSwarm’s retained stacked-NVFP4 source patch.')
        converter_checks = self.projection('converter-verifier.json', self.obs(converter)['verifier'],
                                           'Converter verifier result', 'The tiny conversion compares the packed blocks bit for bit.',
                                           [self.record(converter)])
        before = 'node-check:ingest_nvfp4:converter:2:f9ff60e9'
        trail = self.projection('converter-corrections.json', [self.observations[key] for key in [before, converter]],
                                'Converter correction sequence', 'Original advisory findings and the checked revision.',
                                [self.record(before), self.record(converter)])
        self.step('The converter: JiuwenSwarm writes it, checks pass after repairs',
                  'The worker extended the converter for stacked NVFP4 experts. The verifier passed bit for bit, '
                  'and the revised diff added the requested probe and scale logging.',
                  ['ingest_nvfp4'], converter, [converter_diff, converter_checks, trail], refs=[before],
                  trail=self.trails['ingest_nvfp4'])
        wiring_diff = self.artifact('node-check-e9721ac43159b081a8ae4bc6-diff', 'expert-scale-wiring.diff',
                                    'Expert scale wiring diff', 'Retained changes to expert projection scale arguments.')
        fixture = self.artifact('run-999cc53e8979-result.json', 'expert-scale-fixture.json',
                                'Fixture verifier report', 'Stock and wired KLD, slice limits and scale-free output comparison.')
        fixture_checks = {check['name']: check['detail'] for check in self.obs(wiring)['verifier']['checks']}
        kld, kld_limit = re.search(r'mean KLD ([\d.]+).*limit ([\d.]+)', fixture_checks['nvfp4_kld']).groups()
        error, tolerance = re.search(r'worst max\|d\|/max\|ref\| ([\d.]+) \(tol ([\d.]+)',
                                     fixture_checks['expert_slice']).groups()
        self.step('Expert scale wiring: stock gives NaN, wired matches',
                  f'The fixture recorded stock NaN and wired KLD {kld} (limit {kld_limit}), with worst slice '
                  f'{error} (limit {tolerance}) and byte-identical scale-free output.',
                  ['wire_expert_scales'], wiring, [wiring_diff, fixture], refs=['156a50a3480d41f0bf02c7d43111be96'])
        build = self.artifact('run-b9a0873d31b3-result.json', 'e0-build.json', 'E0 compile receipt',
                              'The source commit and executable from the capped build.')
        smoke = self.artifact('run-14b78261ad4b-rows.json', 'e0-nvfp4-smoke.json', 'E0 cold NVFP4 smoke row',
                              'The recorded request, generated text and timings.')
        smoke_receipt = self.artifact('run-14b78261ad4b-result.json', 'e0-nvfp4-smoke-receipt.json',
                                      'Capped smoke receipt', 'Recorded 96 GiB cgroup limit and smoke outcome.')
        self.step('Base engine E0 compiled and smoke-tested',
                  f"E0 compiled from the agent’s commit. One cold NVFP4 request under the "
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
                                 'Mixed pack census and verifier',
                                 'Native header census, scale preservation and size.',
                                 [self.record(pack), self.record(source_census), self.record(replay_id)])
        receipt = self.artifact('run-d14d2adce4a5-result.json', 'mixed-pack-replay.json', 'Read-only replay receipt',
                                'Original job, original duration and current verification duration.')
        smoke_file = self.artifact('run-3b1a557a0045-rows.json', 'mixed-pack-smoke.json', 'Eight held-out smoke rows',
                                   'Fresh mixed-pack E0 responses from the single capped run.')
        self.step('Quantization: the new mixed 2-bit pack',
                  f"IQ2_XXS gate/up and Q2_K down cover {experts['iq2_xxs']} and {experts['q2_k']} routed tensors. "
                  f"The pack is {self.obs(pack)['bytes'] / 1e9:.1f} GB versus {source_bytes / 1e9:.1f} GB NVFP4. "
                  'The v4 production took '
                  f"{story.replay_duration(replay['duration_seconds'])}; r8 checked it in {self.obs(pack)['replay_seconds']} s, "
                  'and eight held-out E0 prompts produced coherent text.',
                  ['requant_2bit'], pack, [recipe, census, manifest, receipt, smoke_file],
                  refs=[source_census, replay_id, smoke], replay=replay)
        trail = self.trails['requant_2bit']
        note_ids = {event['source'] for event in trail['events'] if event['kind'] == 'note'}
        notes = [note for note in self.notes if note['note_id'] in note_ids or
                 ('requant' in note['text'] and '#reviewer-' in note['text'])]
        checks = [row for row in self.observations.values() if row['kind'] == 'node_check' and
                  row['values']['node_id'] == 'requant_2bit' and row['values']['state'] == 'finished']
        repairs = ['886d66f7ce25412585d92844377871b9', '3b80764e4c9b403abebbc7bf58f9f484',
                   '52511ae961ac45f0ae14a118bbc0eaf8']
        refs = [row['obs_id'] for row in checks] + repairs
        sequence = self.projection('requant-corrections.json', dict(timeline=trail, checks=checks,
                                   specific_fixes=[self.observations[key] for key in repairs]),
                                   'Requant correction sequence', 'Findings, specific fixes, repairs and passing checks.',
                                   [self.record(key) for key in refs])
        note_files = []
        for note in notes:
            name = note['note_id'] + '.json'
            relative = f'operator-inbox/{TASK}/{name}'
            note_files.append(self.evidence(self.graph_home / relative, 'Specific-fix note · ' + name[:8],
                              'Original operator-inbox record.', 'factory_home_file', 'evidence/' + relative,
                              source_home='graph-r8', source_relative_path=relative))
        note_index = self.projection('requant-specific-fix-notes.json', notes, 'Agent help · specific-fix notes',
                                     'Original notes citing the producer, hash convention and evidence limits.',
                                     [dict(path=key['path'], sha256=self.files[key['path']]['sha256']) for key in note_files])
        count = sum(len((row['values'].get('review') or {}).get('findings') or []) for row in checks)
        self.step('Verifiers are experimental: agents keep the graph going',
                  f'The reviewer recorded {count} findings. Agent help with the verifier role identified the v4 '
                  'producer pin, distinguished raw and canonical receipt hashes, and clarified what the replay '
                  'evidence covered. The repaired recipe passed the capsule check.',
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
                                      'Prefill verifier and advisory follow-ups',
                                      'The capsule pass, the reviewer’s four-token tail and the paired output evidence.',
                                      [self.record(key) for key in [check, paired, *followups]])
        load_log = self.artifact('run-e5b36273f07c-server.log', 'prefill-load.log', 'Planned capped load log',
                                 'Recorded buffer allocation, cache and batch settings.')
        plan = self.obs(batch)['plan']
        self.step('Prefill batch plan for the 2-bit engine',
                  f"Batch and micro-batch {plan['batch']} with a {self.obs(paired)['requested_moe_cache_mib']} MiB "
                  f"expert-cache request stayed within {plan['device_budget_mib']} MiB and matched the default-batch "
                  'output. Agent help with the verifier role clarified the recorded four-token tail.',
                  ['size_prefill_batch'], check, [planned, verify_file, load_log], refs=[batch, paired, *followups],
                  trail=self.trails['size_prefill_batch'])
        image_receipt = self.artifact(f'{IMAGE}:receipt', 'image-build-receipt.json', 'Image build receipt',
                                      'The accepted image id and build source commit.')
        image_check = self.artifact(f'{IMAGE}:image-check', 'image-version-check.json', 'Image version check',
                                    'The image ran llama-server --version without a model mount or GPU.')
        image = json.loads((self.stage / image_check['path']).read_bytes())
        delivery = 'labreq-2de8ad02113b333e0c22ae1f:request'
        gate = 'node-check:deliver_to_lab:lab_request:1:6f9e8d04'
        request = self.projection('lab-request-and-gate.json', [self.observations[key] for key in [delivery, gate]],
                                  'Lab request and delivery gate', 'The host gate’s cited image, config and pack digests.',
                                  [self.record(delivery), self.record(gate)])
        self.step('The image and the gate',
                  f"The agent commit {image['source_commit'][:9]} built image {image['image_id'][7:19]} "
                  f"with binary digest {image['executable_sha256'][:12]}. The image passed --version without a model, "
                  'and the delivery gate checked the retained digests.',
                  ['build_image', 'deliver_to_lab'], delivery, [image_receipt, image_check, request],
                  refs=[f'{IMAGE}:build-result', gate])

    def measurements(self):
        report = json.loads(self.report_path.read_bytes())
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
                  f'At warm 2048, TTFT was {warm_a / 1000:.1f} s for historical A, {warm_b / 1000:.1f} s for B '
                  f'and {warm_p / 1000:.1f} s for P. P was {warm_a / warm_p:.1f}× as fast to the first token as A.',
                  ['deliver_to_lab'], primary, [row_projection, report_file, baseline_file, accuracy_file],
                  measurement=measurement)

    def write_bundle(self):
        graph = taskgraph.from_records(self.data)
        node_ids = {node['node_id'] for node in graph['nodes']}
        if any(node not in node_ids for step in self.steps for node in step['graph_nodes']):
            raise ValueError('Replay references a node missing from the recorded R8 graph')
        self.write_json('replay.json', dict(schema=SCHEMA, title=TITLE, order=1, graph_mode='recorded',
                        summary='Ten steps from the owner contract to the delivered image and its lab measurements.',
                        primary_task=TASK, source_homes=['graph-r8'], steps=self.steps))
        for table in ('tasks', *TABLES):
            values = self.data[table] if table != 'artifacts' else [
                self.artifact_rows[row['artifact_id']] for row in self.artifacts]
            self.write_json(f'records/{table}.json', values)
        self.write_json('artifacts.json', self.artifacts)
        self.write_json('key_files.json', {str(step['step']): step['key_files'] for step in self.steps})
        self.write_json('provenance.json', dict(files=self.files, source_homes=['graph-r8'],
                        records={str(step['step']): step['records'] for step in self.steps}))
        self.write_json('MANIFEST.json', {path.relative_to(self.stage).as_posix(): sha(path.read_bytes())
                        for path in sorted(self.stage.rglob('*')) if path.is_file()})


def build(graph, report, baseline, accuracy, out):
    out = out.resolve()
    if out.exists() or out.is_relative_to(graph.resolve()):
        raise ValueError('Output must be a new directory outside the factory graph')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.r8-replay-', dir=out.parent) as directory:
        stage = Path(directory) / 'bundle'
        stage.mkdir()
        try:
            R8Replay(stage, graph.resolve(), report, baseline, accuracy).build()
        except Omitted as exc:
            raise ValueError(f'Required evidence matched the export secret scanner: {exc}') from exc
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
    args = parser.parse_args(argv)
    print(build(args.graph, args.report, args.baseline, args.accuracy, args.out))


if __name__ == '__main__':
    main()
