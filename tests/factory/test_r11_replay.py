"""R11 archive tests use temporary native records and no model jobs."""
import json

import pytest

from jiuwenswarm.factory.export import sha, verify
from jiuwenswarm.factory.store import Store
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService
from scripts.spark.build_r11_replay import TASK, build
from scripts.spark.muse_r11_report import render_lab


def native_home(tmp_path):
    home, contract = tmp_path / 'graph', tmp_path / 'contract.json'
    contract.write_text(json.dumps({'contract_id': TASK, 'version': 11}))
    with Store(home) as store:
        store.create_task(dict(task_id=TASK, contract_id=TASK, objective='Check seeding under the pinned limits',
                               constraints={'contract_sha256': sha(contract.read_bytes())}))
    return home, contract


def test_native_stop_exports_report_and_attaches_under_live_id(tmp_path):
    home, contract = native_home(tmp_path)
    with Store(home) as store:
        data = b'{"may_build": false}'
        store.put_artifact(TASK, 'sealed-premise', data, 'application/json', None)
        check = store.append_observation(TASK, dict(
            kind='node_check', source_artifacts=['sealed-premise'],
            values=dict(node_id='check_seeding_premise', output='premise',
                        passed=True, verifier={'sealed_artifact': 'sealed-premise'}),
        ))
        store.advance_decision(TASK, 0, dict(action={'type': 'stop_missing_prerequisite'},
                                            evidence_ids=[check['obs_id']],
                                            reason_for_change='The measured premise did not authorize a build.'))
    out = build(home, contract, tmp_path / 'archive')
    assert verify(out)
    report = (out / 'reports/lab-report.html').read_text()
    assert 'The measured premise did not authorize a build.' in report
    assert '<th scope="row">E</th>' in report and 'AQBCE = AQBC + E (Run 4).' in report
    assert 'class="metric-chart"' not in report
    assert (out / f'evidence/{sha(data)}.json').read_bytes() == data

    service = FactoryHttpService(roots=[], live_demos=[dict(
        home=str(home), task_id=TASK, title='Run 4', order=4, replay_root=str(out),
    )])
    run_id = service.run_id(home, TASK)
    assert service.detail(run_id)['published_report']['report_kind'] == 'run'
    assert service.file(run_id, 'reports/lab-report.html')['content'] == report


def test_export_requires_a_terminal_decision_and_release_cites_lab(tmp_path):
    home, contract = native_home(tmp_path)
    out = tmp_path / 'archive'
    with pytest.raises(ValueError, match='no terminal decision'):
        build(home, contract, out)
    with Store(home) as store:
        store.advance_decision(TASK, 0, dict(action={'type': 'accept'}, evidence_ids=[],
                                            reason_for_change='Unsubstantiated release'))
    with pytest.raises(ValueError, match='no cited independent lab report'):
        build(home, contract, out)
    assert not out.exists()


def test_owner_032_renders_only_its_pinned_method_note_and_retains_revision_11(tmp_path):
    home = tmp_path / 'graph'
    original = tmp_path / f'{TASK}.json'
    revised = tmp_path / f'{TASK}-amendment-032.json'
    original.write_text(json.dumps({'contract_id': TASK, 'version': 11}))
    revised.write_text(json.dumps({'contract_id': TASK, 'version': 12, 'extensions': {
        'muse.r11-calibration-amendment': {
            'amendment': '032', 'by': 'owner', 'previous_version': 11, 'method_note': 'Recorded notebook calibration.',
        },
    }}))
    before, after = sha(original.read_bytes()), sha(revised.read_bytes())
    with Store(home) as store:
        store.create_task(dict(task_id=TASK, contract_id=TASK, objective='Check the recorded treatment',
                               constraints={'contract_sha256': after}))
        amendment = store.append_observation(TASK, dict(kind='operator_contract_revision', values=dict(
            amendment='032', previous_file=original.name, previous_sha256=before, contract_sha256=after)))
        store.advance_decision(TASK, 0, dict(action={'type': 'report_inconclusive'},
                                            evidence_ids=[amendment['obs_id']], reason_for_change='No target verdict.'))
    out = build(home, revised, tmp_path / 'archive')
    report = (out / 'reports/lab-report.html').read_text()
    assert 'Version 12 (owner amendment 032) accepts the two disjoint notebooks' in report
    assert (out / 'contract-versions' / original.name).read_bytes() == original.read_bytes()
    metadata = json.loads((out / 'replay.json').read_text())
    assert [row['sha256'] for row in metadata['contract_versions']] == [before, after]
    assert metadata['contract_versions'][1]['amendment'] == '032'


def test_lab_render_uses_only_measured_pairs_and_measured_memory():
    output = render_lab({'summary': 'Recorded target verdict'}, {
        'control-load.json': ({'load_seconds': 25, 'peak_process_rss_bytes': 12 * 1024**2}, '../aqbc-load'),
        'seeded-load.json': ({'load_seconds': 30, 'peak_process_rss_bytes': 14 * 1024**2}, '../aqbce-load'),
        'control-speed.json': ({'rows': [{'cell': 'p512', 'client_ttft_ms': 100}]}, '../aqbc-speed'),
        'seeded-speed.json': ({'rows': [{'cell': 'p512', 'client_ttft_ms': 80}]}, '../aqbce-speed'),
        'seeded-startup-fill.json': ({'seed_fill_slots': 42}, '../aqbce-fill'),
    })
    assert 'data-metric="first-token-512"' in output and '1.2× faster (−20%)' in output
    assert 'data-metric="mmlu"' not in output and 'data-metric="first-token-2048"' not in output
    assert 'id="memory"' in output and 'vs AQBC' in output
    assert 'href="../aqbce-load"' in output and 'href="../aqbce-fill"' in output
    assert 'not recorded' in output


def test_release_exports_only_native_lab_attachments(tmp_path):
    home, contract = native_home(tmp_path)
    digest = sha(contract.read_bytes())
    image = 'sha256:' + 'a' * 64
    package_id, request_id = 'labpkg-native', 'labreq-native'
    checks = [dict(test_id='acceptance', check='independent_acceptance', verdict='pass')]
    with Store(home) as store:
        def put(identity, data):
            encoded = json.dumps(data).encode()
            return store.put_artifact(TASK, identity, encoded, 'application/json', None)

        package = put('lab-package:' + package_id, dict(
            package_id=package_id, origin=dict(task_id=TASK, node_id='deliver_to_lab'),
            contract=dict(sha256=digest),
            lab_task=dict(arms={arm: {'subject': 'image'} for arm in ('AQBC', 'AQBCE')}),
            subjects={'image': dict(kind='container_image', identity={'id': image}, verification={'verified': True})},
        ))
        store.append_observation(TASK, dict(
            kind='lab_request', source_artifacts=[package['artifact_id']],
            values=dict(request_id=request_id, package_id=package_id),
        ))
        attached = []
        for name, value in [('control-speed.json', 200), ('seeded-speed.json', 100)]:
            row = put(f'{request_id}:{name}', {'rows': [{'cell': 'p512', 'client_ttft_ms': value}]})
            attached.append(dict(name=name, artifact_id=row['artifact_id'], sha256=row['sha256']))
        result = dict(summary='The independent lab accepted E.', outcome='completed', results=[], checks=checks, not_run=[])
        message = put(f'{request_id}:report.json', {'body': dict(
            result, request_id=request_id, package_id=package_id, contract={'sha256': digest}, files=attached,
        )})
        lab = store.append_observation(TASK, dict(
            kind='lab_report', source_artifacts=[message['artifact_id'], *(row['artifact_id'] for row in attached)],
            values=dict(result, request_id=request_id, package_id=package_id,
                        contract_sha256=digest, valid=True, files=attached),
        ))
        delivery = store.append_observation(TASK, dict(
            kind='node_check', source_artifacts=[package['artifact_id']],
            values=dict(node_id='deliver_to_lab', output='lab_package', passed=True),
        ))
        store.advance_decision(TASK, 0, dict(
            action={'type': 'accept'}, evidence_ids=[delivery['obs_id'], lab['obs_id']],
            reason_for_change='Accepted the cited independent lab result.',
        ))
    out = build(home, contract, tmp_path / 'archive')
    assert verify(out)
    replay = json.loads((out / 'replay.json').read_text())
    assert replay['presentation_header']['report_kind'] == 'lab'
    assert replay['presentation_header']['image_id'] == image
    report = (out / 'reports/lab-report.html').read_text()
    assert '2× faster (−50%)' in report and 'The independent lab accepted E.' in report
    assert all((out / f'evidence/{row["sha256"]}.json').is_file() for row in attached)
