"""Package a read-only Muse Run 2 replay from retained Factory evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from jiuwenswarm.factory import corrections, taskgraph
from jiuwenswarm.factory.controller import TERMINAL
from jiuwenswarm.factory.export import snapshot, verify
from scripts.spark.build_demo_replays import Builder, SCHEMA, TABLES, sha, utc


TASK = 'muse-2bit-demo-r9'
NODES = {
    'pin_inputs': 'Pin the delivered AQB engine',
    'plan_prefix_store': 'Choose the prefix store',
    'build_image': 'Build the configured image',
    'deliver_to_lab': 'Check the factory stage and deliver',
    'measure_engine': 'Measure first requests and follow-up questions',
    'release_gate': 'Check the runtime stage and release',
}
PLACEMENT = ('placement_share_0', 'placement_share_025', 'placement_share_05')
OWNER_AMENDMENTS = {
    '005': ('005-OWNER-checker-all-rows.md', 'Use warm first requests for scoring and retain the cold rows',
            '2f340db14174c35eade4db5969eecb5eb9943eb5d51f73a3da0559816521d814'),
    '006': ('006-OWNER-relax-quiet.md', 'Record background activity without filtering measurements',
            'e7ebafa44d6d1041006bfd39f4ffb881278cbc5fb3c2850b36858f46b7aca013'),
}
OBSERVATION_FIELDS = {
    'taskgraph_patch': 'created decision_rev origin parent_rev patch planner rev task_id',
    'operator_input': 'artifact_id bytes how key kind sha256',
    'operator_contract_revision': 'amendment by contract_file contract_sha256 contract_version graph_rev_after '
                                  'graph_rev_before policy preview previous_file previous_sha256 previous_version '
                                  'reason task_revision',
    'node_contract_final': 'by cc_versions created diff digest final node_contract node_id preliminary_digest rationale',
    'node_contract_refusal': 'by node_contract node_id reason reasons errors preliminary_digest problems '
                             'proposal_digest rationale',
    'node_check': 'entry format found key kind node_id output passed reason refs review runtime_check_revision '
                  'seconds started state verifier',
    'build_result': 'build_wall_seconds delivery failure_stage image_id source_commit status tag target',
    'lab_request': 'request_id package_id lab_task_id contract',
    'capped_run': 'format recipe outcome error seconds memory_cap peak_memory_bytes min_available_bytes node_id attempt_id',
}
PRIVATE_FIELDS = {
    'agent_prompt', 'api_key', 'authorization', 'command', 'container_argv', 'env', 'environment', 'headers',
    'messages', 'mcp_config', 'model_input', 'model_output', 'owner', 'private_key', 'prompt',
    'raw_reply', 'reasoning', 'reviewer_output', 'session', 'session_id', 'stderr', 'stdout',
    'system_prompt', 'tool_calls', 'tool_responses', 'transcript',
}
MAX_JSON = 32 * 1024 * 1024


def pick(obj, fields):
    return {key: obj[key] for key in fields.split() if key in obj}


def public(value):
    if isinstance(value, dict):
        return {key: public(item) for key, item in value.items() if key not in PRIVATE_FIELDS}
    if isinstance(value, list):
        return [public(item) for item in value]
    return value


class Replay(Builder):
    def __init__(self, home, stage, task_id, contract, result):
        super().__init__(home.parent, stage, {})
        self.home = home
        self.task_id = task_id
        self.result_path = result
        self.data = snapshot(home, task_id)
        self.task, = self.data['tasks']
        contract_raw = contract.read_bytes()
        self.contract_sha = sha(contract_raw)
        self.contract = json.loads(contract_raw)
        if self.contract['contract_id'] != self.task['contract_id'] or self.contract_sha != self.task['constraints']['contract_sha256']:
            raise ValueError('The owner contract differs from the native task pin')
        self.graph = taskgraph.from_records(self.data)
        self.nodes = {node['node_id']: node for node in self.graph['nodes']}
        self.observations = self.data['observations']
        self.registry = {item['artifact_id']: item for item in self.data['artifacts']}
        self.sources = {row['values']['key']: row for row in self.observations if row['kind'] == 'operator_input'}
        self.referenced_artifacts = set()
        self.steps = []

    def ref(self, row):
        table = 'observations' if 'obs_id' in row else 'decisions' if 'decision_id' in row else 'tasks'
        return dict(table=table, id=row.get('obs_id', row.get('decision_id', self.task_id)),
                    task_id=self.task_id, source_home='graph')

    def artifact(self, identity):
        item = self.registry[identity]
        location = (self.home / item['location']).resolve(strict=True)
        if (not location.is_relative_to(self.home / 'artifacts') or item['media_type'] != 'application/json'
                or location.stat().st_size != item['size'] or item['size'] > MAX_JSON):
            raise ValueError('Invalid JSON artifact source: ' + identity)
        raw = location.read_bytes()
        if sha(raw) != item['sha256']:
            raise ValueError('Artifact SHA-256 differs: ' + identity)
        self.referenced_artifacts.add(identity)
        source = dict(table='artifacts', source_home='graph', task_id=self.task_id, id=identity, sha256=item['sha256'])
        return json.loads(raw), source

    def sealed(self, node, output):
        checks = self.checks(node, output)
        if not checks:
            return None
        check = checks[-1]
        value = check['values']
        artifact = (value.get('verifier') or {}).get('sealed_artifact')
        if value.get('passed') is not True or not artifact:
            return None
        if artifact not in check['source_artifacts']:
            raise ValueError('Verifier seal is unlinked: ' + check['obs_id'])
        sealed, source = self.artifact(artifact)
        return sealed, [self.ref(check), source]

    def check_files(self, node):
        native = [row for row in self.observations if row['kind'] == 'taskgraph_patch'
                  and any(change.get('node_id') == node for changes in row['values']['patch'].values()
                          if isinstance(changes, list) for change in changes if isinstance(change, dict))]
        return [self.projection(node, 'Node state and Factory checks',
                                dict(node=self.nodes[node], checks=[self.observation(row) for row in self.checks(node)]),
                                [self.ref(row) for row in [*native, *self.checks(node)]])]

    def checks(self, node, output=None):
        return [row for row in self.observations if row['kind'] == 'node_check'
                and row['values'].get('node_id') == node
                and (output is None or row['values'].get('output') == output)]

    def finished_check(self, node, output):
        pin = self.task['constraints'].get('runtime_check_revision')
        for row in reversed(self.checks(node, output)):
            values = row['values']
            if values.get('state') != 'finished':
                continue
            if pin and node == 'measure_engine' and values.get('runtime_check_revision') != pin:
                continue
            if pin and node == 'release_gate':
                found = values.get('found') or {}
                if values.get('passed') and found.get('runtime_check_revision') != pin:
                    continue
                if row['created'] < self.scoring_repin_time():
                    continue
            return row
        return None

    def scoring_repin_time(self):
        for row in reversed(self.observations):
            if (row['kind'] == 'operator_contract_revision'
                    and row['values'].get('contract_sha256') == self.contract_sha):
                return row['created']
        raise ValueError('Missing native revision record for the current runtime policy')

    def projection(self, name, label, data, sources):
        path = f'projections/{name}.json'
        self.write_json(path, public(data))
        raw = (self.stage / path).read_bytes()
        self.files[path] = dict(source='record_projection', sources=sources, display_name=label, sha256=sha(raw), size=len(raw))
        return dict(path=path, label=label)

    def step(self, title, node, say, primary, files, *, refs=(), recorded_summary=None, **extra):
        primary_ref = self.ref(primary)
        self.steps.append(dict(
            step=len(self.steps) + 1, presentation_title=title, node_id=node, graph_nodes=[node],
            say=say, original_kind=primary.get('kind', primary_ref['table'].rstrip('s')),
            original_summary=recorded_summary or primary.get('values', {}).get('reason') or say,
            created=primary['created'], created_utc=utc(primary['created']),
            primary_record=primary_ref['id'], records=[primary_ref, *(self.ref(row) for row in refs if row != primary)],
            key_files=files, files=[item['path'] for item in files], **extra,
        ))

    def observation(self, row):
        kind = row['kind']
        value = pick(row['values'], OBSERVATION_FIELDS[kind])
        if kind == 'node_check' and isinstance(value.get('review'), dict):
            value['review'] = pick(value['review'], 'advisory error findings passed reason summary verdict')
        return public(dict(pick(row, 'obs_id task_id kind created limitations'), values=value,
                           source_artifacts=[a for a in row.get('source_artifacts', []) if a in self.referenced_artifacts]))

    def run_inputs(self):
        owner_path = f'contracts/{self.task_id}.json'
        self.write_json(owner_path, public(self.contract))
        raw = (self.stage / owner_path).read_bytes()
        self.files[owner_path] = dict(source='task_contract_projection', source_sha256=self.contract_sha,
                                      sha256=sha(raw), size=len(raw))
        self.step('Run 2 · reuse the processed document', 'pin_inputs',
                  'Build on AQB with the same mixed pack and server executable. Retain prompt state between document questions.',
                  self.task, [dict(path=owner_path, label='Run 2 owner contract')])
        finals = [row for row in self.observations if row['kind'] == 'node_contract_final']
        refusals = [row for row in self.observations if row['kind'] == 'node_contract_refusal']
        if finals or refusals:
            contracts = self.projection('node-contracts', 'Recorded scheduler changes and bindings',
                                        [self.observation(row) for row in finals + refusals],
                                        [self.ref(row) for row in finals + refusals])
            count = len({row['values']['node_id'] for row in finals})
            first = (finals or refusals)[0]
            self.step('Scheduler node contracts', first['values']['node_id'],
                      f'The graph has {count} finalized node contracts and {len(refusals)} recorded refusal{"" if len(refusals) == 1 else "s"}.',
                      first, [contracts], refs=finals + refusals)

    def amendments(self):
        recorded = [row for row in self.observations if row['kind'] == 'operator_contract_revision']
        rows = []
        refs = []
        for amendment, (filename, title, expected) in OWNER_AMENDMENTS.items():
            matching = [row for row in recorded if row['values'].get('amendment') in (amendment, int(amendment))]
            if len(matching) > 1:
                raise ValueError('Multiple applied revisions for owner amendment ' + amendment)
            receipt = matching[0] if matching else None
            path = self.home.parent.parent / 'bridge' / 'inbox' / filename
            if not receipt and not path.is_file():
                continue
            source = dict(source='owner_inbox', path='bridge/inbox/' + filename, sha256=expected)
            entry = dict(amendment=amendment, title=title, source=source,
                         status='applied' if receipt else 'received')
            if path.is_file():
                raw = path.read_bytes()
                if sha(raw) != expected:
                    raise ValueError('Owner instruction SHA-256 differs: ' + filename)
                entry['owner_instruction'] = raw.decode()
            refs.append(source)
            if receipt:
                revision = self.observation(receipt)
                entry['preview'] = revision['values'].pop('preview', None)
                entry['applied'] = revision
                refs.append(self.ref(receipt))
            rows.append(entry)
        if rows:
            return self.projection('amendments', 'Owner amendments 005 and 006', rows, refs)
        return None

    def planning(self, files):
        summary = None
        extra = {}
        rows = []
        sources = []
        for key in PLACEMENT:
            record = self.sources.get(key)
            if not record or not record['values'].get('artifact_id'):
                continue
            raw, source = self.artifact(record['values']['artifact_id'])
            if source['sha256'] != record['values']['sha256']:
                raise ValueError('Placement artifact differs from its operator input')
            sources.extend([self.ref(record), source])
            rows.append(dict(share=raw['share'], ttft_ms=raw['derived_ttft_ms'],
                             decode_tps=raw['decode_tokens_per_second'], total_s=raw['request_total_ms'] / 1000,
                             quiet=raw['quiet']['status'], quiet_reasons=raw['quiet']['reasons'], source=source))
        if rows:
            files.append(self.projection('placement', 'Placement trial timings and quiet eligibility', rows, sources))
            summary = f'The graph retains {len(rows)} placement trial rows with their quiet eligibility.'
        sealed = self.sealed('plan_prefix_store', 'prefix_plan')
        if sealed:
            plan, refs = sealed
            before, after = plan['aqb_launch_config'], plan['launch_config']
            extra['capsule_diff'] = dict(caption='AQB to AQBC · prefix state', before=before, after=after)
            files.append(self.projection('prefix-plan', 'Verified prefix-store settings and budget',
                                         pick(plan, 'format atlas phase0 phase0b memory aqb_launch_config launch_config '
                                                    'launch_config_sha256 diff'), refs))
            phase = plan['phase0b']
            summary = (f"Placement candidate {plan['phase0']['status']}. Phase 0b reused {phase['cached_tokens']} "
                       f"of {phase['prompt_tokens']} tokens with a {phase['follow_up_ttft_ms'] / 1000:.1f} s follow-up.")
        return summary, extra

    def delivery(self, files, check, request):
        if request:
            values = request['values']
            package_id = values['package_id']
            identity = 'lab-package:' + package_id
            if identity not in request['source_artifacts']:
                raise ValueError('Lab request does not cite the sealed package')
            package, source = self.artifact(identity)
            if package['package_id'] != package_id:
                raise ValueError('Sealed lab package identity differs')
            details = dict(request_id=values['request_id'], package_id=package_id,
                           subjects={name: pick(subject, 'kind identity transfer build_attempt_id')
                                     for name, subject in package['subjects'].items()},
                           tests=package['lab_task']['tests'])
            if check:
                details['host_check'] = pick(check['values'], 'passed state reason found')
            files.append(self.projection('lab-delivery', 'Sealed lab request and subjects', details,
                                         [self.ref(request), source, *([self.ref(check)] if check else [])]))
            if check and check['values']['passed'] is True:
                return 'The host accepted the sealed lab package carrying the configured image and the factory-stage check.'
            return 'The lab request is recorded. The graph has yet to record a passing delivery check.'
        return None

    def standard_rows(self, run, manifest):
        identity = f"run-{run['values']['attempt_id'][:12]}-speed.json"
        if identity not in run['source_artifacts']:
            return None, None
        speed, source = self.artifact(identity)
        if source['sha256'] != manifest.get('files', {}).get('speed.json'):
            raise ValueError('Speed rows do not match the capped measurement manifest')
        cells = {}
        for row in speed['rows']:
            if row['role'] != 'speed':
                continue
            key = (row['state'], row['request'], row['repeat'])
            cell = cells.setdefault(key, {})
            if row['arm'] in cell:
                raise ValueError('Duplicate standard speed row')
            cell[row['arm']] = dict(pick(row, 'cache_prompt derived_ttft_ms request_total_ms decode_tokens_per_second'),
                                    quiet=pick(row['quiet'], 'status reasons'))
        rows = {'cold': [], 'warm': []}
        for (state, request, repeat), arms in cells.items():
            rows[state].append(dict(request=request, repeat=repeat, aqbc=arms.get('AQBC'),
                                    aqb_control=arms.get('AQB-control')))
        return rows, source

    def review_note(self, run, check, manifest):
        if not check:
            return None
        review = check['values'].get('review') or {}
        findings = review.get('findings', [])
        if not review.get('advisory') or not any('null' in finding.get('problem', '').lower() for finding in findings):
            return None
        name = 'p2048-followup-follow-up-0-aqbc.json'
        identity = f"run-{run['values']['attempt_id'][:12]}-{name}"
        expected = manifest.get('files', {}).get(name)
        if identity not in run['source_artifacts'] or not expected:
            return None
        directory = self.home / 'operator-inbox' / self.task_id
        note = next((row for row in reversed(corrections.read_notes(directory, self.task_id))
                     if row['created'] >= check['created'] and expected in row['text']
                     and 'advisory review' in row['text'].lower()), None)
        if not note:
            return None
        measured, source = self.artifact(identity)
        if source['sha256'] != expected or expected == sha(b'null') or not isinstance(measured, dict):
            raise ValueError('Follow-up evidence does not support the operator note')
        note_ref = dict(table='operator-inbox', id=note['note_id'], task_id=self.task_id, source_home='graph')
        facts = dict(source=source, bytes=self.registry[identity]['size'], null_sha256=sha(b'null'),
                     cached_tokens=measured['reuse']['cached_tokens'], ttft_ms=measured['derived_ttft_ms'],
                     quiet_samples=len(measured['quiet']['samples']))
        link = self.projection('runtime-advisory-review', 'Read the original advisory review and operator response',
                               dict(check_id=check['obs_id'], review=review, findings=findings,
                                    operator_note=note, evidence=facts),
                               [self.ref(check), note_ref, self.ref(run), source])
        return link, facts

    def runtime(self, files, run, check):
        if not run:
            return None
        values = run['values']
        manifest = values.get('result') or {}
        refs = [self.ref(run), *([self.ref(check)] if check else [])]
        shown = dict(attempt_id=values['attempt_id'], outcome=values['outcome'], error=values.get('error'),
                     measurement_status=manifest.get('status'), files=manifest.get('files', {}))
        identity = f"run-{values['attempt_id'][:12]}-runtime.json"
        archived = None
        if identity in run['source_artifacts']:
            archived, source = self.artifact(identity)
            if self.result_path is not None and self.result_path.is_file() and sha(self.result_path.read_bytes()) != source['sha256']:
                raise ValueError('Runtime file differs from the retained capped-run artifact')
            shown['initial_lab_checker'] = dict(pick(archived, 'done decision checks summary stage_reached'), source=source)
            refs.append(source)
        rows, source = self.standard_rows(run, manifest)
        if rows is not None:
            shown['warm_first_requests'] = rows['warm']
            shown['cold_first_requests'] = rows['cold']
            shown['first_request_policy'] = dict(
                score='Use every warm pair at 512 and 2048 under the amended checker, with cache reuse disabled on both arms.',
                cold='Display both cold cells for context only. The 512-token AQBC cold request ran first while the pack was still being read.',
            )
            refs.append(source)
        revised = None
        if check:
            value = check['values']
            shown['factory_check'] = pick(value, 'passed state reason verifier runtime_check_revision')
            sealed = (value.get('verifier') or {}).get('sealed_artifact')
            if sealed:
                if sealed not in check['source_artifacts']:
                    raise ValueError('Runtime checker artifact is unlinked')
                revised, source = self.artifact(sealed)
                pin = value.get('runtime_check_revision')
                if pin and revised.get('policy') != pin['policy']:
                    raise ValueError('Sealed runtime verdict differs from the native scoring policy')
                if revised.get('policy'):
                    shown['revised_checker'] = dict(pick(revised, 'policy done decision checks summary stage_reached'),
                                                    source=source, check_id=check['obs_id'])
                    refs.append(source)
                else:
                    revised = None
        if rows is not None:
            shown['revised_check_state'] = 'recorded' if revised else 'pending'
        runtime = revised or archived
        comparisons = ''
        if revised:
            standard = [item for item in revised.get('summary', {}).get('standard', []) if item.get('judged')]
            if standard:
                passing = sum(item['within_tolerance'] for item in standard)
                comparisons = f' {passing}/{len(standard)} warm first-request cells met the same-load tolerance.'
        if revised:
            for pair in revised.get('summary', {}).get('followup', []):
                candidate = pair['candidate']['derived_ttft_ms'] / 1000
                control = pair['control']['derived_ttft_ms'] / 1000
                comparisons += (f" At {pair['request'][1:]} tokens, the follow-up reached first token in "
                                f"{candidate:.2f} s with reuse and {control:.2f} s with reuse off.")
        if runtime:
            accuracy = runtime.get('summary', {}).get('accuracy', {})
            if not accuracy and archived:
                accuracy = archived.get('summary', {}).get('accuracy', {})
            if accuracy.get('mode') == 'identity_check':
                comparisons += (f" MMLU identity {accuracy['status']}: {accuracy['matched_letters']}/{accuracy['question_count']} "
                                f"letters matched AQB, with zero external reuse on {accuracy['zero_external_reuse']} questions.")
                inherited = accuracy['inherited_correct']
                if accuracy['status'] == 'passed' and inherited is not None:
                    comparisons += (
                        f" AQBC inherits AQB's {inherited}/{accuracy['source_question_count']} "
                        f"({accuracy['inherited_accuracy']:.1%}) score by this check."
                    )
                shown['mmlu_identity'] = accuracy
        files.append(self.projection('runtime', 'Same-load speed, follow-up reuse and MMLU identity', shown, refs))
        if check and check['values']['passed'] is True:
            return 'The host runtime check passed.' + comparisons
        if check:
            return f"The host runtime check refused the measurements. {check['values']['reason']}" + comparisons
        return 'The capped attempt returned. The adapted scoring policy awaits the native runtime check.' + comparisons

    def verdict(self, release, measured):
        latest = max(self.data['decisions'], key=lambda item: item['rev'], default={})
        action = latest.get('action', {})
        terminal = action.get('type') in TERMINAL and bool(latest.get('evidence_ids'))
        release_value = release['values'] if release else {}
        output = dict(status='pending', graph_state=self.nodes['release_gate']['state'])
        if release:
            output['release_check'] = pick(release_value, 'passed reason found')
        if measured:
            output['runtime_check'] = pick(measured['values'], 'passed reason')
        if terminal:
            output['terminal_decision'] = dict(pick(latest, 'decision_id evidence_ids reason_for_change'),
                                               action=pick(action, 'type reason'))
            if action['type'] != 'accept':
                output.update(status=action['type'], reason=action.get('reason') or latest.get('reason_for_change'))
                return output, latest
            if (release and release_value.get('passed') is True and output['graph_state'] == 'done'
                    and release['obs_id'] in latest['evidence_ids']
                    and release['obs_id'] in self.nodes['release_gate']['evidence_ids']):
                output.update(status='released', reason=action.get('reason') or latest.get('reason_for_change'))
                return output, latest
        for check, label in ((release, 'release_refused'), (measured, 'runtime_refused')):
            if check and check['values']['passed'] is False:
                output.update(status=label, reason=check['values']['reason'])
                return output, latest if terminal else None
        output['reason'] = ('The release check passed. The terminal acceptance decision is pending.' if release
                            else 'No terminal release verdict is recorded in this snapshot.')
        return output, latest if terminal else None

    def node_steps(self):
        delivered = self.finished_check('deliver_to_lab', 'lab_package')
        request_id = ((delivered or {}).get('values', {}).get('found') or {}).get('request_id')
        request = next((row for row in reversed(self.observations) if row['kind'] == 'lab_request'
                        and (not request_id or row['values']['request_id'] == request_id)), None)
        measured = self.finished_check('measure_engine', 'measurements')
        measurement_refs = ((measured or {}).get('values', {}).get('refs') or {}).get('evidence_ids', [])
        run = next((row for row in reversed(self.observations) if row['kind'] == 'capped_run'
                    and row['values'].get('recipe') == 'muse_r9_measure'
                    and row['values'].get('node_id') == 'measure_engine'
                    and (not measurement_refs or row['obs_id'] in measurement_refs)
                    and (not request_id or row['values'].get('request', {}).get('request_id') == request_id)), None)
        release = self.finished_check('release_gate', 'release')
        verdict, decision = self.verdict(release, measured)
        amendments = self.amendments()
        for node, title in NODES.items():
            checks = self.checks(node)
            own_request = request if node == 'deliver_to_lab' else run if node == 'measure_engine' else None
            final = next((row for row in reversed(self.observations) if row['kind'] == 'node_contract_final'
                          and row['values']['node_id'] == node), None)
            primary = (checks or [own_request or final])[-1]
            files = self.check_files(node)
            summary, extra = None, {}
            if node == 'pin_inputs':
                sealed = self.sealed(node, 'pinned_inputs')
                if sealed:
                    inputs, refs = sealed
                    summary = 'The factory checked the delivered AQB image, server executable, mixed pack and prefill plan before adding prefix reuse.'
                    files.append(self.projection('pinned-inputs', 'Verified AQB image, prefill plan and pack',
                                                 pick(inputs, 'format identity shard_verification'), refs))
            if node == 'plan_prefix_store':
                summary, extra = self.planning(files)
                primary = primary or next((self.sources[key] for key in PLACEMENT if key in self.sources), None)
            if node == 'build_image':
                sealed = self.sealed(node, 'factory_stage')
                if sealed:
                    stage, refs = sealed
                    summary = (f"The factory built image {stage['image_id'].split(':')[-1][:12]} with the prefix-store settings. "
                               "It verified that the image retained the original server binary and mixed pack.")
                    files.append(self.projection('factory-stage', 'Checked image, unchanged inputs and launch config',
                                                 pick(stage, 'format status image_id base_image_id executable_sha256 '
                                                             'launch_config launch_config_sha256 checks'), refs))
            if node == 'deliver_to_lab':
                summary = self.delivery(files, delivered, request)
            if node == 'measure_engine':
                if amendments:
                    files.append(amendments)
                summary = self.runtime(files, run, measured)
                advisory = self.review_note(run, measured, run['values']['result']) if run and measured else None
                if advisory:
                    link, facts = advisory
                    files.append(link)
                    if verdict['status'] == 'released' and len(measured['values']['review']['findings']) == 2:
                        extra['recorded_summary'] = (
                            "The advisory reviewer raised two concerns. It mistook the follow-up file’s SHA-256 "
                            f"({facts['source']['sha256'][:8]}…) for the hash of null ({facts['null_sha256'][:8]}…) "
                            "and asked whether activity on the shared machine had been recorded. "
                            f"The operator checked the file and found {facts['cached_tokens']:,} cached tokens, "
                            f"{facts['ttft_ms'] / 1000:.1f} seconds to first token and {facts['quiet_samples']} activity samples. "
                            "The runtime checker passed, and the release gate accepted the engine."
                        )
            if node == 'release_gate':
                files.append(self.projection('release', 'Release status and native decision', verdict,
                                             [self.ref(row) for row in (release, measured, decision) if row]))
                primary = decision or release or measured or next(
                    row for row in self.observations if row['kind'] == 'taskgraph_patch')
                summary = (f"The factory accepted AQBC in decision {decision['rev']}. The release check linked the delivered image "
                           "to the measured follow-ups and the answer identity check."
                           if verdict['status'] == 'released' else verdict['reason'])
            if primary:
                state = self.nodes[node]['state']
                summary = summary or f'The graph recorded {len(checks)} checks for this node. The node is {state}.'
                self.step(title, node, summary, primary, files,
                          refs=[row for row in [*checks, own_request, final] if row], **extra)
        return verdict['status']

    def write_bundle(self):
        self.run_inputs()
        release_status = self.node_steps()
        self.write_json('replay.json', dict(schema=SCHEMA, title='Run 2 · AQBC prefix store', order=2,
                                           graph_mode='recorded', summary='Run 2 Factory graph and lab evidence.',
                                           primary_task=self.task_id, source_homes=['graph'], release_status=release_status,
                                           steps=self.steps))
        task = pick(self.task, 'task_id objective allowed_effects target budget revision current_decision_rev '
                               'evidence_cursor created contract_id component_cc capability_cc')
        task['constraints'] = pick(self.task['constraints'], 'contract_sha256 contract_immutable contract_revision '
                                   'runtime_check_revision')
        artifacts = [pick(row, 'artifact_id task_id sha256 size media_type complete created attempt_id')
                     for row in self.data['artifacts'] if row['artifact_id'] in self.referenced_artifacts]
        tables = dict(tasks=[task], artifacts=artifacts, evaluations=[], uploads=[])
        tables['observations'] = [self.observation(row) for row in self.observations if row['kind'] in OBSERVATION_FIELDS]
        tables['decisions'] = [dict(pick(row, 'decision_id task_id rev parent_rev evidence_ids created reason_for_change'),
                                   action=pick(row['action'], 'type node_id operation output reason'))
                               for row in self.data['decisions']]
        tables['attempts'] = [dict(pick(row, 'attempt_id task_id kind state jobq_id started ended created result_refs'),
                                   request=pick(row['request'], 'node_id recipe request_id package_id tag target'))
                              for row in self.data['attempts']]
        for table in ('tasks', *TABLES):
            self.write_json(f'records/{table}.json', public(tables[table]))
        self.write_json('artifacts.json', artifacts)
        self.write_json('key_files.json', {str(step['step']): step['key_files'] for step in self.steps})
        self.write_json('provenance.json', dict(files=self.files, records={str(step['step']): step['records'] for step in self.steps}))


def build(home, task_id, contract, result, output):
    home, output = home.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(home):
        raise ValueError('Replay output must be a new directory outside the native Factory home')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / 'bundle'
        stage.mkdir()
        replay = Replay(home, stage, task_id, contract, result)
        replay.write_bundle()
        replay.write_json('MANIFEST.json', {f.relative_to(stage).as_posix(): sha(f.read_bytes())
                                            for f in stage.rglob('*') if f.is_file()})
        verify(stage)
        stage.rename(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('home', 'contract', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--result', type=Path, help='Optional original lab runtime.json to verify against its graph artifact')
    parser.add_argument('--task', default=TASK)
    args = parser.parse_args()
    build(args.home, args.task, args.contract, args.result, args.output)
