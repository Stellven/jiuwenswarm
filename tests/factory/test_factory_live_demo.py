import json

import pytest
from fastapi import HTTPException

from jiuwenswarm.factory.export import sha
from jiuwenswarm.factory.store import Store
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService


def registration(home, archive):
    return dict(home=str(home), task_id='native-demo', title='Run 4 · Expert cache seeding', order=4,
                replay_root=str(archive))


def archive_bundle(archive, task, home, *, report=b'<h1>Run report</h1>'):
    archive.mkdir()
    files = {
        'records/tasks.json': json.dumps([task]).encode(),
        'replay.json': json.dumps(dict(
            schema='factory.curated-replay/1', primary_task=task['task_id'], source_homes=[home.name],
            title='Archived demo', graph_mode='recorded', order=4, steps=[],
            presentation_header=dict(objective=task['objective'], outcome='Stopped', report_kind='run'),
        )).encode(),
        'reports/lab-report.html': report,
    }
    for relative, contents in files.items():
        target = archive / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
    (archive / 'MANIFEST.json').write_text(json.dumps({key: sha(raw) for key, raw in files.items()}))


def test_demo_appears_after_admission_and_updates_under_one_read_only_id(tmp_path):
    home, archive = tmp_path / 'graph', tmp_path / 'export'
    service = FactoryHttpService(roots=[], live_demos=[registration(home, archive)])
    assert service.listing()['live_demos_enabled']
    assert service.listing()['runs'] == []

    with Store(home) as store:
        task = store.create_task(dict(task_id='native-demo', objective='Recorded demo objective'))
        native, = service.listing()['runs']
        run_id = native['id']
        assert run_id == service.run_id(home, 'native-demo')
        assert native['contract_demo'] and native['demo_order'] == 4 and native['status'] == 'live'
        assert native['name'].startswith('Run 4')
        assert native['read_only'] and native['live_demo']
        detail = service.detail(run_id)
        assert detail['run_state']['state'] == 'idle'
        assert detail['controls'] is None
        assert not detail['published_report']

        with pytest.raises(HTTPException) as forbidden:
            service.operator(run_id, 'hold', 'work', 'Viewer is read-only')
        assert forbidden.value.status_code == 403

        archive_bundle(archive, task, home)
        assert not service.detail(run_id)['published_report']
        with pytest.raises(HTTPException) as missing:
            service.file(run_id, 'reports/lab-report.html')
        assert missing.value.status_code == 404

        store.put_artifact('native-demo', 'sealed-example', b'{}', 'application/json', None)
        store.advance_decision('native-demo', 0, dict(action=dict(type='stop_missing_prerequisite'),
                                                     evidence_ids=[], reason_for_change='Recorded stop'))
        detail = service.detail(run_id)
        assert detail['run']['id'] == run_id and detail['run']['status'] == 'replay'
        assert detail['run_state']['state'] == 'stopped'
        assert detail['published_report']['report_kind'] == 'run'
        assert any('sealed-example' in file['artifact_ids'] for file in detail['files'])
        assert service.file(run_id, 'reports/lab-report.html')['content'] == '<h1>Run report</h1>'

        (archive / 'reports/lab-report.html').write_text('<h1>Modified</h1>')
        assert not service.detail(run_id)['published_report']


def test_archive_with_different_admission_does_not_attach(tmp_path):
    home, archive = tmp_path / 'graph', tmp_path / 'export'
    service = FactoryHttpService(roots=[], live_demos=[registration(home, archive)])
    with Store(home) as store:
        task = store.create_task(dict(task_id='native-demo', objective='Recorded demo objective'))
        archive_bundle(archive, {**task, 'created': task['created'] - 10}, home)
        store.advance_decision('native-demo', 0, dict(action=dict(type='stop_missing_prerequisite'),
                                                     evidence_ids=[], reason_for_change='Recorded stop'))
    assert not service.detail(service.run_id(home, 'native-demo'))['published_report']
