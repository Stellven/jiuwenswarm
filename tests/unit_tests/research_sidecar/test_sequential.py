"""Configuration-only interface fixture: queue control and retained real bytes."""
import asyncio
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from jiuwenswarm.research_sidecar.client import ClientError
from jiuwenswarm.research_sidecar.sequential import SequentialRunner, create_campaign, read_json, atomic, cleanup_owned, load_campaign
from jiuwenswarm.research_sidecar.sequential_cases import validate_cases


class InterfaceFixture:
    """A generic supported interface, deliberately not an app execution substitute."""
    def __init__(self):
        self.submissions = []; self.states = {}; self.collected = []; self.active = None
        self.lose_reply = False; self.unresolved = False; self.break_download = False
        self.body = b'actual interface-fixture artifact bytes\n'

    async def readiness(self): return {'ready': True, 'build_id': 'fixture-build', 'client_contract_version': '1.0.0', 'pins': {}}
    async def context(self): return {'defaults': {'workspace_id': 'fixture-workspace'}}
    async def prepare_intake(self, task, uploads, workspace_id=None):
        return {'qualified': True, 'intake_ref': {'id': task}, 'submission_defaults': {'id': 'fixture-submission'}}
    async def submit(self, payload):
        assert self.active is None, 'second task dispatched before prior collection'
        self.submissions.append(payload); run_id = 'fixture-' + str(len(self.submissions)); self.active = run_id
        self.states[payload['client_request_id']] = {'run_id': run_id, 'client_request_id': payload['client_request_id'], 'revision': 1, 'status': 'completed'}
        if self.lose_reply: raise httpx.ReadTimeout('fixture lost reply')
        return self.states[payload['client_request_id']]
    async def reconcile(self, request):
        if self.unresolved: raise ClientError('not found', status_code=404)
        return self.states[request]
    async def status(self, run_id): return next(v for v in self.states.values() if v['run_id'] == run_id)
    async def events(self, run_id, after=0): return {'events': [], 'metrics': None, 'next_after': after}
    async def artifacts(self, run_id):
        from jiuwenswarm.research_sidecar.evidence import canonical
        files = [{'artifact_id': 'actual-output', 'path': 'output.txt', 'size': len(self.body), 'sha256': hashlib.sha256(self.body).hexdigest(), 'media_type': 'text/plain'}]
        manifest = {'run_id': run_id, 'artifacts': files, 'execution_terminal': True}
        return {**manifest, 'manifest_sha256': hashlib.sha256(canonical(manifest)).hexdigest()}
    async def download_artifact(self, run_id, artifact_id, destination, **kwargs):
        if self.break_download: raise OSError('fixture interrupted collection')
        atomic(destination, self.body, exclusive=True)
    async def confirm_collection(self, run_id, sha256, artifacts):
        assert sha256 == (await self.artifacts(run_id))['manifest_sha256']
        self.collected.append(run_id); self.active = None
        return {'status': 'confirmed'}


def campaign(tmp_path, cases=None):
    store = tmp_path / 'cases'; inputs = tmp_path / 'inputs'; output = tmp_path / 'results'
    for folder in (store, inputs, output): folder.mkdir()
    source = store / 'cases.json'
    source.write_text(json.dumps({'schema_version': 'sequential-cases:1', 'cases': cases or [{'id': 'first', 'task': 'First task'}, {'id': 'second', 'task': 'Second task'}]}))
    return create_campaign(source, inputs, output, campaign_id='queue', endpoint='http://generic:5175', expected_build='fixture-build')


def drive(client, folder, value):
    runner = SequentialRunner(client, folder, value, progress=lambda _: None)
    try: return asyncio.run(runner.run())
    finally: runner.close()


def test_queue_collects_bytes_before_next_submit_and_keeps_results(tmp_path):
    folder, value = campaign(tmp_path); client = InterfaceFixture()
    assert drive(client, folder, value) == 0
    assert len(client.submissions) == 2
    for ident in ('first-r1', 'second-r1'):
        assert (folder / 'runs' / ident / 'artifacts/output.txt').read_bytes() == client.body
        row = read_json(folder / 'runs' / ident / 'run_record.json')
        assert row['collection_state'] == 'complete'
    assert cleanup_owned(folder, value)['results_retained'] is True
    assert (folder / 'report.md').is_file()


def test_uncertain_delivery_reconciles_before_any_new_dispatch(tmp_path):
    folder, value = campaign(tmp_path); client = InterfaceFixture()
    client.lose_reply = client.unresolved = True
    assert drive(client, folder, value) == 3
    assert len(client.submissions) == 1
    assert drive(client, folder, value) == 3
    assert len(client.submissions) == 1
    with pytest.raises(ValueError): cleanup_owned(folder, value)
    client.lose_reply = client.unresolved = False
    assert drive(client, folder, value) == 0
    assert len(client.submissions) == 2


def test_collection_retry_never_reexecutes_task(tmp_path):
    folder, value = campaign(tmp_path); client = InterfaceFixture(); client.break_download = True
    assert drive(client, folder, value) == 3
    assert len(client.submissions) == 1
    row = read_json(folder / 'runs/first-r1/run_record.json')
    assert row['execution_state'] == 'completed' and row['collection_state'] == 'failed'
    client.break_download = False
    assert drive(client, folder, value) == 0
    assert len(client.submissions) == 2
    assert read_json(folder / 'runs/first-r1/run_record.json')['errors'][0]['category'] == 'collection_failure'


def test_large_archive_collection_resumes_verified_bytes_and_original_manifest(tmp_path):
    import io
    import zipfile
    from jiuwenswarm.research_sidecar.evidence import canonical
    class LargeInterface(InterfaceFixture):
        def __init__(self):
            super().__init__(); self.list_calls = 0; self.archive_calls = 0; self.fail_receipt = True
        async def artifacts(self, run_id):
            self.list_calls += 1
            files = []; artifacts = []; bodies = []
            for index in range(129):
                path = 'notes/note-' + str(index) + '.txt'; body = ('Actual fixture bytes ' + str(index)).encode()
                ref = {'id': 'note:' + str(index), 'sha256': hashlib.sha256(body).hexdigest()}
                files.append({'path': path, 'artifact_ref': ref, 'media_type': 'text/plain', 'audience': 'researcher'})
                artifacts.append({'artifact_id': hashlib.sha256(canonical([path, ref])).hexdigest(), 'path': path, 'size': len(body), 'sha256': ref['sha256'], 'media_type': 'text/plain'})
                bodies.append((path, body))
            retrieval = {'schema_version': '1.0.0', 'id': 'retrieval:large', 'run_id': run_id, 'audience': 'researcher', 'artifact_refs': [item['artifact_ref'] for item in files], 'files': files, 'redactions': []}
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('client_retrieval.json', canonical(retrieval))
                for path, body in bodies: archive.writestr(path, body)
            self.zip = buffer.getvalue()
            manifest = {'schema_version': '1.0.0', 'run_id': run_id, 'audience': 'researcher', 'artifacts': artifacts, 'execution_terminal': True}
            self.manifest = {**manifest, 'manifest_sha256': hashlib.sha256(canonical(manifest)).hexdigest()}
            return self.manifest
        async def stream_export_archive(self, run_id, destination, **kwargs):
            self.archive_calls += 1; destination.write_bytes(self.zip)
        async def confirm_collection(self, run_id, sha256, artifacts):
            assert sha256 == self.manifest['manifest_sha256'] and artifacts == self.manifest['artifacts']
            if self.fail_receipt: raise ClientError('fixture interrupted receipt', status_code=503)
            self.active = None
            return {'status': 'confirmed'}
    folder, value = campaign(tmp_path, [{'id': 'large', 'task': 'Archive task', 'limits': {'max_files': 8}}])
    # Exercise the default for campaigns frozen before archive_member_limit existed.
    value['cases'][0]['limits'].pop('archive_member_limit')
    client = LargeInterface()
    assert drive(client, folder, value) == 3
    original = (folder / 'runs/large-r1/artifacts/originals.zip').read_bytes()
    assert original == client.zip
    client.fail_receipt = False
    assert drive(client, folder, value) == 0
    assert len(client.submissions) == client.list_calls == client.archive_calls == 1
    row = read_json(folder / 'runs/large-r1/run_record.json')
    assert row['archive_collection']['verified_members'] == 129
    assert len(row['artifacts']) <= 8 and row['collection_state'] == 'complete'
    assert (folder / 'runs/large-r1/artifacts/originals.zip').read_bytes() == original


def test_deadline_cancellation_pending_blocks_next_dispatch_and_resume_does_not_resend(tmp_path):
    class PendingCancellation(InterfaceFixture):
        def __init__(self): super().__init__(); self.cancel_calls = 0
        async def submit(self, payload):
            value = await super().submit(payload)
            if len(self.submissions) == 1: value['status'] = 'in_progress'
            return value
        async def cancel(self, run_id, request_id):
            self.cancel_calls += 1
            return {'status': 'pending'}
    folder, value = campaign(tmp_path, [
        {'id': 'first', 'task': 'Task one', 'limits': {'deadline_s': .001, 'cancel_grace_s': .005, 'poll_s': .001}},
        {'id': 'second', 'task': 'Task two'}])
    client = PendingCancellation()
    assert drive(client, folder, value) == 3
    assert len(client.submissions) == client.cancel_calls == 1
    assert read_json(folder / 'runs/first-r1/run_record.json')['execution_state'] == 'cancellation_pending'
    assert drive(client, folder, value) == 3
    assert len(client.submissions) == client.cancel_calls == 1
    client.states[client.submissions[0]['client_request_id']].update(status='halted', revision=2)
    assert drive(client, folder, value) == 2  # app execution halted, not a correctness judgement
    assert len(client.submissions) == 2
    assert read_json(folder / 'runs/first-r1/run_record.json')['collection_state'] == 'complete'


def test_user_cancellation_stops_queued_dispatch_until_explicit_resume(tmp_path):
    folder, value = campaign(tmp_path); client = InterfaceFixture()
    atomic(folder / 'cancellation_requested.json', {'requested_at': 'fixture', 'handled': False})
    assert drive(client, folder, value) == 3
    assert not client.submissions
    assert drive(client, folder, value) == 0
    assert len(client.submissions) == 2


def test_expired_absolute_deadline_is_retained_without_dispatch(tmp_path):
    folder, value = campaign(tmp_path, [{'id': 'expired', 'task': 'Task', 'deadline_at': '2000-01-01T00:00:00Z'}])
    client = InterfaceFixture()
    assert drive(client, folder, value) == 2
    assert not client.submissions
    row = read_json(folder / 'runs/expired-r1/run_record.json')
    assert row['execution_state'] == 'timed_out' and row['collection_state'] == 'not_applicable'


def test_acl_owned_output_accepts_writable_host_acl_but_foreign_tree_stays_strict(tmp_path, monkeypatch):
    import errno
    from jiuwenswarm.research_sidecar.evidence import _owned_acl_directory_mode
    folder, value = campaign(tmp_path)
    owned = folder / 'owned-output'; owned.mkdir()
    foreign = tmp_path / 'foreign-output'; foreign.mkdir()
    def denied(*args, **kwargs): raise PermissionError(errno.EPERM, 'filesystem ACL owns mode')
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'chmod', denied)
        _owned_acl_directory_mode(owned, 0o2750)
        with pytest.raises(PermissionError): _owned_acl_directory_mode(foreign, 0o2750)
    assert not list(owned.glob('.acl-access-*'))


def test_incomplete_campaign_creation_is_refused_before_any_submission(tmp_path):
    folder, value = campaign(tmp_path)
    (folder / 'runs/second-r1/run_record.json').unlink()
    with pytest.raises(ValueError, match='creation is incomplete'):
        load_campaign(folder)


def test_trusted_commands_are_explicit_and_capture_exit_without_quality_score(tmp_path):
    import sys
    folder, value = campaign(tmp_path, [{'id': 'prepared', 'task': 'Task', 'setup': [{'trusted': True, 'command': [sys.executable, '-c', 'import pathlib; pathlib.Path("prepared.txt").write_text("prepared"); print("preparation")'], 'outputs': ['prepared.txt']}]}])
    client = InterfaceFixture()
    assert drive(client, folder, value) == 0
    row = read_json(folder / 'runs/prepared-r1/run_record.json')
    assert row['commands'][0]['exit_code'] == 0
    assert (folder / 'runs/prepared-r1/workspace/prepared.txt').read_text() == 'prepared'
    assert 'score' not in row


def test_secret_environment_is_referenced_and_stdout_is_redacted(tmp_path, monkeypatch):
    import sys
    secret = 'fixture-secret-token-keep-private'
    monkeypatch.setenv('FIXTURE_API_KEY', secret)
    folder, value = campaign(tmp_path, [{'id': 'secret', 'task': 'Task', 'setup': [{
        'trusted': True, 'env': {'FIXTURE_API_KEY': {'from_env': 'FIXTURE_API_KEY'}},
        'command': [sys.executable, '-c', 'import os,sys; v=os.environ["FIXTURE_API_KEY"]; sys.stdout.write("a"*65530+v+"end"); sys.stderr.write(v)']}]}])
    assert drive(InterfaceFixture(), folder, value) == 0
    assert secret.encode() not in (folder / 'runs/secret-r1/commands/setup-command-1.stdout').read_bytes()
    assert b'[REDACTED]' in (folder / 'runs/secret-r1/commands/setup-command-1.stdout').read_bytes()
    assert secret not in (folder / 'campaign.json').read_text()
    assert secret not in (folder / 'report.json').read_text()


@pytest.mark.parametrize('case', [
    {'id': 'bad', 'task': 'task', 'inputs': [{'path': '../answers.txt'}]},
    {'id': 'bad', 'task': 'task', 'setup': [{'command': ['python', 'generated.py']}]},
    {'id': 'bad', 'task': 'task', 'limits': {'deadline_s': float('inf')}},
    {'id': 'bad', 'task': 'task', 'setup': [{'trusted': True, 'command': ['echo', 'ok'], 'env': {'API_KEY': 'literal-private'}}]},
])
def test_invalid_untrusted_or_unbounded_cases_are_rejected(case):
    with pytest.raises(ValueError): validate_cases({'schema_version': 'sequential-cases:1', 'cases': [case]})


def test_case_plan_source_is_preselected_and_persists_across_resume(tmp_path):
    folder, value = campaign(tmp_path, [{'id': 'planned', 'task': 'Planned task', 'plan_source': 'planned'},
        {'id': 'static', 'task': 'Static task', 'plan_source': 'static'}, {'id': 'default', 'task': 'Use app default'}])
    client = InterfaceFixture()
    assert drive(client, folder, value) == 0
    assert [r.get('plan_source') for r in client.submissions] == ['planned', 'static', None]
    assert drive(client, folder, value) == 0
    assert len(client.submissions) == 3
    with pytest.raises(ValueError, match='plan_source'):
        validate_cases({'schema_version': 'sequential-cases:1', 'cases': [{'id': 'bad', 'task': 'x', 'plan_source': 'fallback'}]})
