"""Publish the terminal, read-only Run 4 attachment from native Factory evidence."""
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
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService
from scripts.spark.build_demo_replays import Builder, SCHEMA, TABLES, sha, utc
from scripts.spark.build_muse_lab_reports import LAB_STYLE, REPORT_PATH, STYLE, a, arm_names_box, p
from scripts.spark.build_r9_replay import OBSERVATION_FIELDS, pick, public
from scripts.spark.muse_r11_report import ARMS, render_lab
from scripts.spark.muse_report_checks import node_check_label, render_factory_checks, snapshot_activity

TASK = 'muse-2bit-demo-r11'
TITLE = 'Run 4 · Expert cache profile seeding (AQBCE)'
CALIBRATION_AMENDMENT = 'muse.r11-calibration-amendment'
CALIBRATION_METHOD = (
    'Version 12 (owner amendment 032) accepts the two disjoint notebooks recorded by the profile, '
    'replacing the original revision 11 calibration input after post-profile review.'
)
MAX_FILE = 16 * 1024 * 1024
FILE_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
PUBLIC_OBSERVATIONS = OBSERVATION_FIELDS | {
    'lab_report': 'request_id package_id valid problems contract contract_sha256 outcome summary results checks not_run files',
}


def recorded_decision(row):
    return dict(pick(row, 'decision_id task_id rev parent_rev evidence_ids created reason_for_change'),
                action=pick(row['action'], 'type node_id reason'))


class Replay(Builder):
    def __init__(self, home, stage, contract_path):
        super().__init__(home.parent, stage, {})
        self.home = home
        with tempfile.TemporaryDirectory(prefix='r11-snapshot-') as temporary:
            copied = Path(temporary)
            FactoryHttpService.copy_store(home, copied)
            self.data = snapshot(copied, TASK)
        self.task, = self.data['tasks']
        raw = contract_path.read_bytes()
        self.contract_sha = sha(raw)
        self.contract = json.loads(raw)
        self.version = self.contract.get('version')
        marker = (self.contract.get('extensions') or {}).get(CALIBRATION_AMENDMENT) or {}
        self.owner_amendment = (self.version == 12 and marker.get('amendment') == '032'
                                and marker.get('by') == 'owner' and marker.get('previous_version') == 11)
        if ((self.version != 11 and not self.owner_amendment) or self.contract.get('contract_id') != TASK
                or self.task.get('contract_id') != TASK
                or self.task['constraints'].get('contract_sha256') != self.contract_sha):
            raise ValueError('The Run 4 contract differs from the admitted task revision')
        self.contract_file = self.copy(
            contract_path, f'contracts/{TASK}.json',
            {'source': 'task_contract', 'display_name': f'Owner contract · revision {self.version}'},
            expected=self.contract_sha,
        )
        self.contract_versions = self.versions(contract_path, marker)
        self.registry = {row['artifact_id']: row for row in self.data['artifacts']}
        self.exported = {}

    def versions(self, contract_path, marker):
        current = dict(version=self.version, path=self.contract_file, sha256=self.contract_sha)
        if not self.owner_amendment:
            return [current]
        revisions = [row['values'] for row in self.data['observations'] if row['kind'] == 'operator_contract_revision'
                     and str(row['values'].get('amendment')).zfill(3) == '032'
                     and row['values'].get('contract_sha256') == self.contract_sha]
        if len(revisions) != 1:
            raise ValueError('Revision 12 needs its recorded owner amendment')
        receipt, = revisions
        if (receipt.get('previous_file') != f'{TASK}.json'
                or not re.fullmatch(r'[0-9a-f]{64}', receipt.get('previous_sha256', ''))):
            raise ValueError('Owner amendment 032 must retain its revision 11 pin')
        parent = contract_path.with_name(receipt['previous_file'])
        original = json.loads(parent.read_bytes())
        if original.get('contract_id') != TASK or original.get('version') != 11:
            raise ValueError('Owner amendment 032 has an invalid predecessor contract')
        path = self.copy(parent, 'contract-versions/' + parent.name,
                         {'source': 'task_contract', 'display_name': 'Owner contract · revision 11'},
                         expected=receipt['previous_sha256'])
        return [dict(version=11, path=path, sha256=receipt['previous_sha256']),
                dict(current, amendment='032', reason=marker.get('method_note') or CALIBRATION_METHOD)]

    def artifact(self, artifact_id, label, *, expected=None):
        row = self.registry.get(artifact_id)
        if not row or not row['complete'] or row['size'] > MAX_FILE or (expected and row['sha256'] != expected):
            raise ValueError('Missing, incomplete or inconsistent sealed source: ' + artifact_id)
        raw_path = self.home / row['location']
        path = raw_path.resolve(strict=True)
        if path != raw_path or not path.is_relative_to(self.home / 'artifacts') or path.stat().st_size != row['size']:
            raise ValueError('Sealed artifact does not match its native location and size')
        raw = path.read_bytes()
        parsed = json.loads(raw) if row['media_type'] == 'application/json' else None
        if raw != scrub_bytes(raw) or (parsed is not None and sanitize(parsed) != parsed):
            raise ValueError('Public artifact requires redaction: ' + artifact_id)
        suffix = '.json' if parsed is not None else path.suffix
        if not re.fullmatch(r'\.[A-Za-z0-9_-]{1,12}', suffix):
            suffix = '.txt'
        target = self.copy(path, f'evidence/{row["sha256"]}{suffix}',
                           dict(source='factory_home_artifact', source_home=self.home.name, artifact_id=artifact_id,
                                display_name=label), expected=row['sha256'])
        self.exported[artifact_id] = dict(
            pick(row, 'artifact_id task_id media_type sha256 size complete created producer_attempt'),
            exported_path=target, exported_sha256=row['sha256'],
        )
        return parsed, target

    def cited_lab(self, terminal, observations):
        reports = [row for row in observations if row['kind'] == 'lab_report'
                   and row['obs_id'] in terminal['evidence_ids'] and row['values'].get('valid') is True]
        if not reports:
            return None
        if len(reports) != 1:
            raise ValueError('Terminal decision cites more than one valid target report')
        report, = reports
        values = report['values']
        package_id = values['package_id']
        request_id = values['request_id']
        request = next((row for row in observations if row['kind'] == 'lab_request'
                        and row['values'].get('request_id') == request_id
                        and row['values'].get('package_id') == package_id), None)
        package_artifact = 'lab-package:' + package_id
        if (request is None or package_artifact not in request['source_artifacts']
                or values.get('contract_sha256') != self.contract_sha):
            raise ValueError('Lab report does not bind the native request and pinned contract')
        package, package_path = self.artifact(package_artifact, 'Sealed target test requirements')
        if (package['origin']['task_id'] != TASK or package['contract']['sha256'] != self.contract_sha
                or package['package_id'] != package_id):
            raise ValueError('Sealed target package does not match the admitted task')
        subjects = [package['subjects'][package['lab_task']['arms'][arm]['subject']] for arm in ARMS]
        images = {item['identity']['id'] for item in subjects
                  if item['kind'] == 'container_image' and item.get('verification', {}).get('verified') is True}
        if len(images) != 1 or any(item.get('identity', {}).get('id') not in images for item in subjects):
            raise ValueError('Lab package does not bind both arms to the same verified image')
        image, = images
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
            raise ValueError('Lab package is missing a complete image digest')

        message_id = f'{request_id}:report.json'
        if message_id not in report['source_artifacts']:
            raise ValueError('Missing source message for the imported lab report')
        message, message_path = self.artifact(message_id, 'Imported target lab verdict')
        body = message['body']
        if (body['request_id'] != request_id or body['package_id'] != package_id
                or body['contract']['sha256'] != self.contract_sha
                or any(body.get(key) != values.get(key) for key in ('summary', 'outcome', 'results', 'checks', 'not_run'))):
            raise ValueError('Imported lab observation differs from its sealed report message')
        json_files = {}
        raw_by_name = {file['name']: file for file in body['files']}
        for ref in values.get('files', []):
            artifact_id, name = ref['artifact_id'], ref['name']
            if artifact_id not in report['source_artifacts'] or not FILE_NAME.fullmatch(name):
                raise ValueError('Lab attachment is outside the imported report evidence')
            # The native lab manager may retain other message attachments. Only the
            # report's own declared sources can contribute measurements here.
            if name not in raw_by_name:
                continue
            if raw_by_name[name]['sha256'] != ref['sha256'] or name in json_files:
                raise ValueError('Lab attachment does not match its declared source')
            data, path = self.artifact(artifact_id, name, expected=ref['sha256'])
            if isinstance(data, dict):
                json_files[name] = data, '../' + path
        if terminal['action']['type'] == 'accept':
            delivery = any(row['kind'] == 'node_check' and row['obs_id'] in terminal['evidence_ids']
                           and row['values'].get('node_id') == package['origin'].get('node_id')
                           and row['values'].get('output') == 'lab_package'
                           and row['values'].get('passed') is True for row in observations)
            passed = any(row['check'] == 'independent_acceptance' and row['verdict'] == 'pass'
                         for row in values['checks'])
            if not delivery or not passed or values['outcome'] != 'completed':
                raise ValueError('Release requires the cited delivery check and independent passing lab verdict')
        return values, image, json_files, (package_path, message_path)

    def historical_load(self, replay_root):
        if replay_root is None:
            return None
        relative = 'reports/evidence/a-load.json'
        source = replay_root / relative
        manifest = json.loads((replay_root / 'MANIFEST.json').read_text())
        if source.resolve(strict=True) != source or relative not in manifest or source.stat().st_size > MAX_FILE:
            raise ValueError('Historical A load is outside the published replay')
        path = self.copy(source, 'evidence/a-reference-load.json',
                         dict(source='published_run_1_load', display_name='Published A load receipt'),
                         expected=manifest[relative])
        return json.loads((self.stage / path).read_bytes()), '../' + path

    def build(self, *, historical):
        terminal = max(self.data['decisions'], key=lambda row: row['rev'], default=None)
        if terminal is None or terminal['action']['type'] not in TERMINAL:
            raise ValueError('Native Run 4 has no terminal decision')
        action = terminal['action']['type']
        observations = self.data['observations']
        lab = self.cited_lab(terminal, observations)
        if action == 'accept' and lab is None:
            raise ValueError('Native Run 4 release has no cited independent lab report')
        outcome = ('AQBCE released.' if action == 'accept' else
                   'AQBCE was not released. AQBC remains the released engine.')
        kind = 'lab' if lab else 'run'
        image = lab[1] if lab else None
        decision_path = 'projections/terminal-decision.json'
        self.write_json(decision_path, recorded_decision(terminal))

        for row in observations:
            if row['obs_id'] not in terminal['evidence_ids'] or row['kind'] != 'node_check':
                continue
            artifact_id = (row['values'].get('verifier') or {}).get('sealed_artifact')
            if artifact_id and artifact_id in row.get('source_artifacts', []):
                self.artifact(artifact_id, node_check_label(row['values']))

        body = ('<p class="verdict"><strong>' + escape(outcome) + '</strong></p>' + arm_names_box()
                + '<h2>Native terminal decision</h2>' + p(terminal['reason_for_change'])
                + '<p>' + a('../' + decision_path, f'Factory decision revision {terminal["rev"]}') + '</p>')
        if lab:
            values, _, sources, (package_path, message_path) = lab
            body += '<p>Delivered image <code>' + escape(image) + '</code></p>'
            body += render_lab(values, sources, historical_load=self.historical_load(historical),
                               report_source='../' + message_path)
            body += '<p>' + a('../' + package_path, 'Sealed target test requirements') + ' · '
            body += a('../' + message_path, 'Recorded target lab verdict') + '</p>'
        else:
            has_build = any(row['kind'] == 'build_result' and row['values'].get('image_id') for row in observations)
            if not has_build:
                body += p('No candidate image is recorded for Run 4.')
            body += p('The terminal decision cites no imported target lab report.')
        if self.owner_amendment:
            body += '<h2>Method</h2>' + p(CALIBRATION_METHOD)
        body += '<h2>Evidence</h2><ul>'
        body += ''.join('<li>' + a('../' + item['path'], f'Pinned revision {item["version"]} contract') + '</li>'
                        for item in self.contract_versions)
        body += ''.join('<li>' + a('../' + path, description['display_name']) + '</li>'
                        for path, description in self.files.items() if path.startswith('evidence/'))
        body += '</ul>'
        title = 'Run 4 · ' + ('Lab report' if lab else 'Run report')
        target = self.stage / REPORT_PATH
        target.parent.mkdir()
        body += render_factory_checks(snapshot_activity(self.data, self.home, self.contract), stage=self.stage)
        target.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                          '<meta name="viewport" content="width=device-width, initial-scale=1">'
                          f'<title>{title}</title><style>{STYLE}{LAB_STYLE if lab else ""}</style>'
                          f'</head><body><main><h1>{title}</h1>{body}</main></body></html>\n', encoding='utf-8')
        self.write_replay(terminal, outcome, kind, image)

    def write_replay(self, terminal, outcome, kind, image):
        observations = [
            dict(pick(row, 'obs_id task_id kind source_artifacts created limitations'),
                 values=pick(row['values'], PUBLIC_OBSERVATIONS[row['kind']]))
            for row in self.data['observations'] if row['kind'] in PUBLIC_OBSERVATIONS
        ]
        task = pick(self.task, 'task_id contract_id objective allowed_effects target budget revision created '
                              'current_decision_rev evidence_cursor component_cc')
        task['constraints'] = pick(self.task['constraints'], 'contract_sha256 contract_revision contract_immutable')
        files = [{'path': REPORT_PATH, 'label': 'Attached report'},
                 {'path': 'projections/terminal-decision.json', 'label': 'Native terminal decision'}]
        records = [(task, 'tasks', task['task_id'], 'task', task['objective'], None, [
            {'path': item['path'], 'label': f'Pinned revision {item["version"]} contract'}
            for item in self.contract_versions
        ])]
        for row in observations:
            values = row['values']
            if row['kind'] in {'node_check', 'taskgraph_patch', 'lab_report', 'node_contract_final',
                               'node_contract_refusal', 'operator_contract_revision'}:
                summary = values.get('summary') or values.get('reason') or values.get('output') or row['kind']
                records.append((row, 'observations', row['obs_id'], row['kind'], summary, values.get('node_id'), [
                    {'path': self.exported[aid]['exported_path'],
                     'label': self.files[self.exported[aid]['exported_path']]['display_name']}
                    for aid in row.get('source_artifacts', []) if aid in self.exported
                ]))
        records.sort(key=lambda event: event[0]['created'])
        records.append((terminal, 'decisions', terminal['decision_id'], terminal['action']['type'],
                        terminal['reason_for_change'], terminal['action'].get('node_id'), files))
        steps = [
            dict(step=index, original_kind=kind, original_summary=summary, presentation_title=kind.replace('_', ' ').capitalize(),
                 primary_record=identity, created=row['created'], created_utc=utc(row['created']),
                 records=[dict(table=table_name, id=identity, source_home=self.home.name, task_id=TASK)],
                 node_id=node, graph_nodes=[node] if node else [], key_files=links)
            for index, (row, table_name, identity, kind, summary, node, links) in enumerate(records, 1)
        ]
        self.write_json('replay.json', public(dict(
            schema=SCHEMA, title=TITLE, order=4, graph_mode='recorded', primary_task=TASK,
            source_homes=[self.home.name], summary=outcome, steps=steps,
            presentation_header=dict(objective=task['objective'], outcome=outcome, report_kind=kind, image_id=image),
            contract_versions=self.contract_versions,
        )))
        tables = dict(tasks=[task], observations=observations,
                      decisions=[recorded_decision(row) for row in self.data['decisions']],
                      attempts=[pick(row, 'attempt_id task_id kind state created started ended request result_refs')
                                for row in self.data['attempts']], artifacts=list(self.exported.values()),
                      evaluations=[], uploads=[])
        for table_name in ('tasks', *TABLES):
            self.write_json(f'records/{table_name}.json', public(tables[table_name]))
        self.write_json('artifacts.json', list(self.exported.values()))
        self.write_json('provenance.json', {'files': self.files})


def build(home, contract, output, *, historical=None):
    home, contract, output = (Path(path).resolve() for path in (home, contract, output))
    if (home / 'controller.lock').is_file() and FactoryHttpService._running(home):
        raise ValueError('Wait for the native controller to finish before exporting')
    if output.exists() or output.is_relative_to(home):
        raise ValueError('Output must be a new directory outside the live home')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / 'bundle'
        stage.mkdir()
        replay = Replay(home, stage, contract)
        replay.build(historical=Path(historical).resolve() if historical is not None else None)
        replay.write_json('MANIFEST.json', {
            path.relative_to(stage).as_posix(): sha(path.read_bytes()) for path in stage.rglob('*') if path.is_file()
        })
        verify(stage)
        stage.rename(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('home', 'contract', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--historical-a', type=Path, help='Verified Run 1 replay bundle for historical A memory')
    args = parser.parse_args()
    print(build(args.home, args.contract, args.output, historical=args.historical_a))
