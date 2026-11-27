"""Build the public Run 3 replay from the terminal native Factory record."""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import re
import tempfile

from jiuwenswarm.factory.controller import TERMINAL
from jiuwenswarm.factory.export import snapshot, verify
from jiuwenswarm.factory.redact import sanitize, scrub_bytes
from scripts.spark.build_demo_replays import Builder, SCHEMA, TABLES, sha, utc
from scripts.spark.build_muse_lab_reports import REPORT_PATH, STYLE, a, arm_names_box, p, table
from scripts.spark.build_r9_replay import OBSERVATION_FIELDS, pick, public
from scripts.spark.muse_replay_presentation import FACTORY, RUNTIME, check, node

TASK = 'muse-2bit-demo-r10'
TITLE = 'Run 3 · Batched routed-expert launches (AQBCD)'
METHOD = 'Batch compatible routed-expert launches when the pinned decode path still submits them separately.'
NODES = {
    'pin_inputs': node('Pin the released AQBC engine', 'Pin the baseline image, executable, pack and prefill configuration.',
                       pinned_inputs=check(FACTORY, 'Check identity and compatibility of the starting engine.')),
    'trace_dispatch': node('Trace routed-expert dispatch', 'Follow actual decode shapes through the pinned backend and determine whether D has an eligible launch.',
                           dispatch_trace=check(FACTORY, 'Check the dispatch trace and fixture evidence before allowing candidate work.',
                                                verifier_role='CC verifier')),
    'verify_fixtures': node('Verify candidate fixtures', 'Check the gated batching method, fallback and off switch on fixtures.',
                            fixtures=check(FACTORY, 'Check the method and fixture cases.', verifier_role='CC verifier')),
    'build_image': node('Package the identified candidate', 'Build and identify the candidate only after it passes the dispatch gate and fixture checks.'),
    'deliver_to_lab': node('Deliver the sealed test request', 'Hand the candidate image and its test requirements to the lab agent.'),
    'measure_engine': node('Check delivered behavior on the target', 'Measure the delivered engine on Spark and retain the lab verdict.',
                           measurements=check(RUNTIME, 'Assess the delivered test requirements.', role='Lab acceptance')),
    'release_gate': node('Decide release', 'Use the lab verdict for the exact delivered candidate.'),
}
STOP_REASONS = {
    'already_batched': 'The pinned AQBC backend already batches the eligible decode shapes.',
    'no_eligible_shapes': 'The dispatch trace found no eligible decode shapes.',
    'unresolved': 'The dispatch trace did not establish eligibility.',
}
PUBLIC_OBSERVATIONS = OBSERVATION_FIELDS | {
    'dispatch_gate': 'eligibility may_build reason node_id',
}
MAX_FILE = 16 * 1024 * 1024
FIXTURE_CASES = {
    'iq2_projection': 'Gate or up projection (IQ2_XXS)',
    'q2_down': 'Down projection (Q2_K)',
    'iq2_gate_up_pair': 'Separate gate and up projections (IQ2_XXS)',
    'iq2_adjacent_gate_up': 'Compatible adjacent gate/up (IQ2_XXS)',
}


class Replay(Builder):
    def __init__(self, home, stage, contract, task_id):
        super().__init__(home.parent, stage, {})
        self.home = home
        self.task_id = task_id
        self.data = snapshot(home, task_id)
        self.task, = self.data['tasks']
        self.registry = {row['artifact_id']: row for row in self.data['artifacts']}
        self.observations = self.data['observations']
        self.steps = []
        raw = contract.read_bytes()
        self.contract_sha = sha(raw)
        self.contract = json.loads(raw)
        if (self.contract.get('version') != 10 or self.contract.get('contract_id') != TASK
                or self.task['contract_id'] != TASK
                or self.contract_sha != self.task['constraints']['contract_sha256']):
            raise ValueError('Revision 10 contract does not match the recorded native task pin')
        self.baseline = self.contract['extensions']['muse.r10-dispatch']['baseline']
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', self.baseline['image_id']):
            raise ValueError('Missing exact baseline image identity')
        self.contract_file = self.copy(contract, f'contracts/{self.task["contract_id"]}.json',
                                       dict(source='task_contract', display_name='Owner contract · revision 10'),
                                       expected=self.contract_sha)

    def ref(self, row):
        for field, table in (('obs_id', 'observations'), ('decision_id', 'decisions'), ('task_id', 'tasks')):
            if field in row:
                return dict(table=table, id=row[field], source_home='graph', task_id=self.task_id)
        raise ValueError('Record is missing a native identity')

    def projection(self, path, value, label, refs):
        self.write_json(path, public(value))
        raw = (self.stage / path).read_bytes()
        self.files[path] = dict(source='record_projection', display_name=label, sources=[self.ref(row) for row in refs],
                                sha256=sha(raw), size=len(raw))
        return dict(path=path, label=label)

    def copy_artifact(self, identity, label, *, diff=False):
        row = self.registry[identity]
        if not row['complete'] or row['size'] > MAX_FILE:
            raise ValueError('Incomplete or oversized public evidence artifact: ' + identity)
        location = self.home / row['location']
        path = location.resolve(strict=True)
        if (not path.is_relative_to(self.home / 'artifacts') or path != location
                or path.stat().st_size != row['size'] or not path.is_file()):
            raise ValueError('Artifact location or size differs from the native registry')
        suffix = {'application/json': '.json', 'text/x-diff': '.diff'}.get(row['media_type'], path.suffix)
        if not re.fullmatch(r'\.[A-Za-z0-9_-]{1,12}', suffix):
            suffix = '.txt'
        raw = path.read_bytes()
        if diff:
            if not raw.startswith((b'diff --git ', b'--- ')) or b'\n+++ ' not in raw:
                raise ValueError('Expected a native unified source diff or patch')
            suffix = '.diff'
        if scrubbed(raw, row['media_type']):
            raise ValueError('Public artifact requires redaction: ' + identity)
        exported = self.copy(path, f'evidence/{row["sha256"]}{suffix}',
                             dict(source='factory_home_artifact', source_home='graph', artifact_id=identity,
                                  source_path=row['location'], display_name=label), expected=row['sha256'])
        if not any(item['artifact_id'] == identity for item in self.artifacts):
            self.artifacts.append(dict(pick(row, 'artifact_id task_id media_type sha256 size complete created producer_attempt'),
                                       exported_path=exported, exported_sha256=row['sha256']))
        return dict(path=exported, label=label)

    def checks(self, node_id, *, output=None):
        return [row for row in self.observations if row['kind'] == 'node_check'
                and row['values'].get('node_id') == node_id
                and (output is None or row['values'].get('output') == output)]

    def sealed(self, node_id, output, label):
        for row in reversed(self.checks(node_id, output=output)):
            values = row['values']
            if values.get('state') in ('started', 'running'):
                continue
            if values.get('passed') is not True:
                break
            identity = (values.get('verifier') or {}).get('sealed_artifact')
            if identity not in row.get('source_artifacts', []) or not identity:
                break
            file = self.copy_artifact(identity, label)
            return row, file, json.loads((self.stage / file['path']).read_bytes())
        raise ValueError(f'No current sealed evidence for {node_id}/{output}')

    def observation(self, row):
        fields = PUBLIC_OBSERVATIONS[row['kind']]
        return dict(pick(row, 'obs_id task_id kind created limitations'), values=pick(row['values'], fields),
                    source_artifacts=row.get('source_artifacts') or [])

    def baseline_evidence(self):
        baseline = self.projection('projections/baseline.json', self.baseline, 'Pinned AQBC identity', [self.task])
        pin = self.contract['extensions']['muse.r10-dispatch'].get('parent_reference')
        if not pin:
            return [baseline]
        relative = pin['path'].removeprefix('${FACTORY_MUSE_DEMO}/')
        root = self.home.parent.parent
        source = (root / relative).resolve(strict=True)
        if not source.is_relative_to(root):
            raise ValueError('Parent reference is outside the campaign root')
        label = 'AQBC baseline evidence and digests'
        path = self.copy(source, 'evidence/aqbc-parent-reference.json',
                         dict(source='pinned_parent_reference', display_name=label, source_path=relative),
                         expected=pin['sha256'])
        parent = json.loads((self.stage / path).read_bytes())
        if any(parent.get(field) != value for field, value in self.baseline.items()):
            raise ValueError('Parent reference differs from the rev10 baseline')
        return [baseline, dict(path=path, label=label)]

    def linked_trace_sources(self, trace):
        root = self.home.parent.parent
        dispatch_root = root / 'lab/r10-aqbcd/dispatch'
        sources = {}
        fixture = trace.get('fixture', {}).get('cases', {})
        refs = {}
        if trace.get('raw_trace'):
            refs['trace'] = (trace['raw_trace'], 'Original pre-graph dispatch trace')
        if fixture:
            for case_id, label in FIXTURE_CASES.items():
                refs[case_id] = (fixture[case_id]['log'], label + ' fixture log')
        for key, (ref, label) in refs.items():
            relative = ref['path']
            path = (root / relative).resolve(strict=True)
            if not path.is_relative_to(dispatch_root) or path != root / relative or path.stat().st_size > MAX_FILE:
                raise ValueError('Invalid public dispatch source path or size')
            copy = self.copy(path, f'evidence/dispatch/{path.name}',
                             dict(source='verified_dispatch_input', display_name=label, source_path=relative),
                             expected=ref['sha256'])
            sources[key] = dict(path=copy, label=label)
        return sources

    def scheduler_capability_note(self, finals):
        fixture = next((row for row in reversed(finals)
                        if row['kind'] == 'node_contract_final' and row['values']['node_id'] == 'verify_fixtures'), None)
        earlier_trace = next((row for row in finals
                               if row['kind'] == 'node_contract_final' and row['values']['node_id'] == 'trace_dispatch'), None)
        if not fixture or not earlier_trace:
            return '', None, None
        cc = 'engine.gpu_kernel_lab'
        before = earlier_trace['values'].get('cc_versions', {}).get(cc)
        after = fixture['values'].get('cc_versions', {}).get(cc)
        verifiers = fixture['values'].get('final', {}).get('verifiers', [])
        if not before or not after or before == after or not any(
            output.get('verifier') == cc + '.verify_candidate' for output in verifiers
        ):
            return '', None, None
        source = f'sessions/{self.task_id}.scheduler.jsonl'
        path = self.home / source
        if path.resolve() != path or not path.is_file() or path.stat().st_size > MAX_FILE:
            return '', None, None
        payload = path.read_bytes()
        for number, line in reversed(list(enumerate(payload.splitlines(keepends=True), 1))):
            row = json.loads(line)
            if (row.get('event_type') != 'chat.final'
                    or not row.get('session_id', '').startswith(self.task_id + '-scheduler-verify_fixtures-')):
                continue
            text = row.get('content', '')
            if not isinstance(text, str):
                continue
            match = re.search(r'The only eligible capsule, `engine\.gpu_kernel_lab` v'
                              + re.escape(before) + r', declares only `evaluate`, `benchmark`, and `trace_dispatch` in `cc\.yaml`\.', text)
            if (not match or 'verify_candidate' not in text
                    or 'I did not submit a proposal' not in text
                    or scrub_bytes(match[0].encode()) != match[0].encode()):
                continue
            excerpt = dict(path=source, line=number, text=match[0])
            proof = self.projection('projections/scheduler-capability-gap.json', dict(
                excerpt=excerpt, source_sha256=sha(payload), line_sha256=sha(line),
                earlier_capsule_version=before, finalized_fixture_capsule_version=after,
                earlier_final=self.ref(earlier_trace), fixture_final=self.ref(fixture),
            ), 'Scheduler capability gap and finalized repair', [earlier_trace, fixture])
            summary = (f' The scheduler reported that v{before} lacked the required fixture verifier and submitted no proposal.'
                       f' The later fixture final bound verify_candidate at v{after}.')
            return summary, proof, excerpt
        return '', None, None

    def step(self, title, node_id, method, result, rows, files, *, quote=None):
        first = rows[0]
        primary = self.ref(first)
        kind = first.get('kind', primary['table'].rstrip('s'))
        native = first.get('values') or {}
        summary = (native.get('reason') or native.get('rationale') or first.get('reason_for_change')
                   or first.get('objective') or kind)
        self.steps.append(dict(
            step=len(self.steps) + 1, presentation_title=title, node_id=node_id, graph_nodes=[node_id],
            original_kind=kind, original_summary=summary, created=first['created'],
            created_utc=utc(first['created']), records=[self.ref(row) for row in rows], primary_record=primary['id'],
            say=f'{method} In this run: {result}', presenter_line=method, key_files=files,
            files=[file['path'] for file in files], **({'quotes': [quote]} if quote else {}),
        ))

    def report(self, outcome, candidate, terminal, trace, files, *, lab_result, trace_sources):
        path = self.stage / REPORT_PATH
        path.parent.mkdir()
        links = ''.join(f'<li>{a("../" + item["path"], item["label"])}</li>' for item in files)
        body = f'<p class="verdict"><strong>{escape(outcome)}</strong></p>'
        if not trace['may_build']:
            body += p(f"The node verifier passed the dispatch trace with may_build false. The final decision (rev {terminal['rev']}) stopped the graph.")
        body += arm_names_box()
        body += '<h2>Starting engine</h2>' + p('AQBC is the released baseline.') + '<p>Image <code>'
        body += escape(self.baseline['image_id']) + '</code></p>'
        body += '<h2>Dispatch eligibility</h2>' + p(STOP_REASONS.get(trace['eligibility'], 'The trace established an eligible decode shape.'))
        if trace.get('fixture', {}).get('cases'):
            body += p('Before graph setup, the operator captured one-token CUDA graph executions in the exact pinned AQBC CUDA backend using synthetic tensors. The native CC verifier then checked the capture digests and rederived the result from the pinned source, mixed-pack headers and Nsight records.')
            body += p('A matvec launch is one recorded execution of the routed quantized matrix-vector kernel in the CUDA graph. Its grid spans the selected routes. Total kernels also count activation quantization and the separate gated operation where present.')
            fixture = trace['fixture']['cases']
            rows = []
            for case_id, label in FIXTURE_CASES.items():
                case = fixture[case_id]
                grids = {tuple(launch['grid']) for launch in case['launches'] if launch['name'] == 'mul_mat_vec_q'}
                rows.append((escape(label), str(case['operands']['routes']), str(case['matvec_launch_count']),
                             str(case['launch_count']), escape(', '.join(' × '.join(map(str, grid)) for grid in sorted(grids))),
                             a('../' + trace_sources[case_id]['path'], 'Fixture log')))
            body += table(['Projection shape', 'Selected routes', 'Matvec launches', 'Total kernels', 'Matvec grid', 'Evidence'],
                          rows, 'Measured synthetic one-token dispatch on Spark')
            body += p('The two separate gate/up projections each cover every route in one launch. The compatible adjacent pair also fused in the fixture. External weight scales break this adjacency on the pinned Muse path where those scales are applied.')
            body += p('This checked dispatch behavior only. The fixture did not load Muse or measure full-model timing.')
        reason = public(sanitize(decision(terminal))).get('reason_for_change')
        if reason:
            body += p(reason)
        body += '<h2>Candidate and measurement</h2>'
        body += p(f'Candidate image {candidate}.' if candidate else 'No candidate image was built.')
        if not trace['may_build']:
            body += p('The dispatch gate ended the run before delivery. No candidate source change or target benchmark was run.')
        elif lab_result:
            body += p('The links below retain the native delivery and available lab evidence for the identified candidate.')
        else:
            body += p('No target lab verdict was recorded for this candidate.')
        body += '<h2>Method</h2>' + p(METHOD)
        body += p('Trace the pinned backend and check eligibility before changing source. When a change is eligible, the factory checks the fixtures and fallback before delivering the image and test requirements to the lab.')
        body += '<h2>Evidence</h2><ul>' + links + '</ul>'
        title = 'Run 3 · Lab report' if trace['may_build'] else 'Run 3 · Run report'
        path.write_text(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{title}</title><style>{STYLE}</style></head><body><main><h1>{title}</h1>'
            + body + '</main></body></html>\n', encoding='utf-8')
        return dict(path=REPORT_PATH, label=title)

    def build(self, *, candidate_diff=None, instrumentation_diff=None):
        terminal = self.data['decisions'][-1] if self.data['decisions'] else None
        action = (terminal or {}).get('action', {}).get('type')
        if action not in TERMINAL:
            raise ValueError('The native Factory run has no terminal decision')
        trace_row, trace_file, trace = self.sealed('trace_dispatch', 'dispatch_trace', 'Dispatch trace and eligibility')
        eligibility = trace['eligibility']
        if eligibility not in {*STOP_REASONS, 'eligible'} or trace.get('may_build') is not (eligibility == 'eligible'):
            raise ValueError('Dispatch eligibility and build permission disagree')
        identity = trace.get('identity', {})
        for field in ('image_id', 'binary_sha256', 'pack_manifest_sha256', 'launch_config_sha256'):
            if field in self.baseline and identity.get(field) != self.baseline[field]:
                raise ValueError('Sealed trace differs from the baseline: ' + field)
        if terminal['action'].get('eligibility', eligibility) != eligibility:
            raise ValueError('Native terminal eligibility differs from the sealed trace')
        build_rows = [row for row in self.observations if row['kind'] == 'build_result']
        image = next((row['values'].get('image_id') for row in reversed(build_rows)
                      if row['values'].get('image_id')), None)
        if image and not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
            raise ValueError('Candidate image identity is not a content digest')
        if not trace['may_build']:
            if (action not in {'stop_missing_prerequisite', 'report_inconclusive'} or build_rows or candidate_diff
                    or trace_row['obs_id'] not in terminal.get('evidence_ids', [])):
                raise ValueError('Pre-build stop disagrees with the native terminal, trace or candidate evidence')
        if image and (image == self.baseline['image_id'] or not candidate_diff):
            raise ValueError('Built candidate requires a distinct image and its recorded source diff')
        lab_result = None
        evidence = []
        if action == 'accept':
            if not image or not self.checks('deliver_to_lab'):
                raise ValueError('Release requires delivery of the identified candidate image')
            lab_row, lab_file, lab_result = self.sealed('measure_engine', 'measurements', 'Target lab result')
            if lab_row['obs_id'] not in terminal.get('evidence_ids', []):
                raise ValueError('Release decision does not cite the sealed lab result')
            evidence.append(lab_file)

        contract_file = dict(path=self.contract_file, label='Owner contract · revision 10')
        baseline = self.baseline_evidence()
        self.step('The batched-launch contract', 'pin_inputs', METHOD, 'The owner pinned AQBC as the baseline.',
                  [self.task], [contract_file, *baseline])
        finals = [row for row in self.observations if row['kind'] in ('node_contract_final', 'node_contract_refusal')]
        if finals:
            contracts = self.projection('projections/node-contracts.json', [self.observation(row) for row in finals],
                                        'Recorded scheduler changes and bindings', finals)
            note, proof, excerpt = self.scheduler_capability_note(finals)
            self.step('Scheduler node contracts', finals[0]['values']['node_id'],
                      'Finalize the node contracts with checks for each stage.',
                      f'The scheduler recorded {len(finals)} finalization or refusal records.' + note,
                      finals, [contracts, proof] if proof else [contracts], quote=excerpt)
        pins = self.checks('pin_inputs', output='pinned_inputs')
        if pins:
            self.step('Pin the released AQBC engine', 'pin_inputs', NODES['pin_inputs']['method'],
                      'The node verifier recorded the AQBC input checks.', [pins[-1], *pins[:-1]], baseline)
        files = [trace_file]
        trace_sources = self.linked_trace_sources(trace)
        files.extend(trace_sources.values())
        trace_refs = [trace_row]
        if instrumentation_diff:
            input_refs = [row for row in self.observations if row['kind'] == 'operator_input'
                          and row['values'].get('key') == 'dispatch_fixture_diff'
                          and row['values'].get('artifact_id') == instrumentation_diff
                          and row['values'].get('sha256') == self.registry[instrumentation_diff]['sha256']]
            trace_refs.extend(input_refs)
            files.append(self.check_diff(instrumentation_diff, 'Pre-graph dispatch probe instrumentation diff', trace_refs))
        fixture_summary = fixture_line(trace)
        self.step('Trace routed-expert dispatch', 'trace_dispatch', NODES['trace_dispatch']['method'],
                  'The native CC verifier rechecked the operator-supplied dispatch trace. ' + fixture_summary
                  + STOP_REASONS.get(eligibility, 'The dispatch check established an eligible shape.'), trace_refs, files)
        evidence.extend([*baseline, *files])
        diff_file = None
        if candidate_diff:
            diff_file = self.check_diff(candidate_diff, 'Candidate D source diff', self.checks('verify_fixtures') + build_rows)
            evidence.append(diff_file)
        for node_id in ('verify_fixtures', 'build_image', 'deliver_to_lab', 'measure_engine', 'release_gate'):
            rows = self.checks(node_id)
            if not rows:
                continue
            artifact_files = [self.copy_artifact(identity, f'{NODES[node_id]["title"]} · {identity}')
                              for identity in dict.fromkeys(identity for row in rows if row['values'].get('passed') is True
                                                           for identity in (row.get('source_artifacts') or []))
                              if identity in self.registry and self.registry[identity]['media_type'] == 'application/json']
            if node_id == 'build_image' and diff_file:
                artifact_files.insert(0, diff_file)
            projection = self.projection(f'projections/{node_id}.json', [self.observation(row) for row in rows],
                                         NODES[node_id]['title'] + ' checks', rows)
            self.step(NODES[node_id]['title'], node_id, NODES[node_id]['method'],
                      f'The factory recorded {len(rows)} checks.', rows, [*artifact_files, projection])
            evidence.extend([*artifact_files, projection])
        outcome = ('Stopped before build. AQBC remains the released engine.' if not trace['may_build']
                   else 'AQBCD released.' if action == 'accept'
                   else 'AQBCD was not accepted. AQBC remains the released engine.')
        decision_file = self.projection('projections/terminal-decision.json', decision(terminal),
                                        'Native terminal decision', [terminal])
        links = {file['path']: file for file in [*evidence, decision_file]}
        report = self.report(outcome, image, terminal, trace, links.values(), lab_result=lab_result,
                             trace_sources=trace_sources)
        final_node = (terminal['action'].get('node_id') or ('trace_dispatch' if not trace['may_build'] else 'deliver_to_lab'))
        self.step('Recorded outcome', final_node, 'Decide whether to proceed from the recorded checks.',
                  outcome, [terminal], [report, decision_file])

        self.write_json('replay.json', dict(schema=SCHEMA, title=TITLE, order=3, graph_mode='recorded', summary=outcome,
                                           primary_task=self.task_id, source_homes=['graph'], node_presentation=NODES,
                                           presentation_header=dict(objective='Trace routed-expert decode dispatch in AQBC and evaluate a gated batching change if eligible.',
                                                                    outcome=outcome, image_id=image,
                                                                    report_kind='lab' if trace['may_build'] else 'run'),
                                           contract_versions=[dict(version=10, path=self.contract_file, sha256=self.contract_sha)],
                                           steps=self.steps))
        task = pick(self.task, 'task_id objective allowed_effects target budget revision current_decision_rev '
                               'evidence_cursor created contract_id component_cc capability_cc')
        task['constraints'] = pick(self.task['constraints'], 'contract_sha256 contract_immutable contract_revision')
        tables = dict(tasks=[task], artifacts=self.artifacts, evaluations=[], uploads=[],
                      decisions=[decision(row) for row in self.data['decisions']],
                      observations=[self.observation(row) for row in self.observations if row['kind'] in PUBLIC_OBSERVATIONS],
                      attempts=[dict(pick(row, 'attempt_id task_id kind state jobq_id started ended created result_refs'),
                                     request=pick(row.get('request') or {}, 'node_id recipe request_id package_id tag target'))
                                for row in self.data['attempts']])
        for table in ('tasks', *TABLES):
            self.write_json(f'records/{table}.json', public(tables[table]))
        self.write_json('artifacts.json', self.artifacts)
        self.write_json('provenance.json', dict(files=self.files, records={str(step['step']): step['records'] for step in self.steps}))

    def check_diff(self, identity, label, linked):
        references = {value for row in linked for value in (row.get('source_artifacts') or [])}
        if identity not in references:
            raise ValueError('Diff is not linked to its native check or build record')
        return self.copy_artifact(identity, label, diff=True)


def scrubbed(raw, media_type):
    if raw != scrub_bytes(raw):
        return True
    if media_type == 'application/json':
        parsed = json.loads(raw)
        return sanitize(parsed) != parsed
    return False


def fixture_line(trace):
    cases = trace.get('fixture', {}).get('cases')
    if not cases:
        return ''
    iq2, down, pair, fused = (cases[case] for case in FIXTURE_CASES)
    return (
        f'The pinned backend’s synthetic fixtures recorded {iq2["matvec_launch_count"]} matvec launch for '
        f'{iq2["operands"]["routes"]} routes in an IQ2_XXS gate or up projection, '
        f'{down["matvec_launch_count"]} for {down["operands"]["routes"]} routes in Q2_K down, '
        f'{pair["matvec_launch_count"]} for the separate gate/up pair and '
        f'{fused["matvec_launch_count"]} for the fused adjacent fixture. '
    )


def decision(row):
    return dict(pick(row, 'decision_id task_id rev parent_rev evidence_ids created reason_for_change'),
                action=pick(row['action'], 'type node_id operation output reason eligibility'))


def build(home, contract, output, task_id=TASK, *, candidate_diff=None, instrumentation_diff=None):
    home, output = home.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(home):
        raise ValueError('Replay output must be a new directory outside the native Factory home')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / 'bundle'
        stage.mkdir()
        replay = Replay(home, stage, contract, task_id)
        replay.build(candidate_diff=candidate_diff, instrumentation_diff=instrumentation_diff)
        replay.write_json('MANIFEST.json', {f.relative_to(stage).as_posix(): sha(f.read_bytes())
                                            for f in stage.rglob('*') if f.is_file()})
        verify(stage)
        stage.rename(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('home', 'contract', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--task', default=TASK)
    parser.add_argument('--candidate-diff', help='Native artifact ID for the verified D change')
    parser.add_argument('--instrumentation-diff', help='Native artifact ID for the trace instrumentation, if any')
    args = parser.parse_args()
    build(args.home, args.contract, args.output, args.task, candidate_diff=args.candidate_diff,
          instrumentation_diff=args.instrumentation_diff)
