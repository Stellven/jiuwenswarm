"""Independent IF016 historical custody; no execution owner or model resources."""
import copy
import hashlib
import io
import json
import stat
import zipfile

import pytest

from jiuwenswarm.research.contracts import Principal, ResearchError, validate
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes


def historical_store(root):
    store = SQLiteRunStore(root)
    def blob(data): return store.put_blob(data, media_type='application/octet-stream')
    def record(kind, body):
        if kind in {'evaluation-runtime', 'evaluation-request', 'evaluation-event', 'evaluation-terminal'}:
            validate('urn:ai4r:private:' + kind + ':1', body)
        return store.append_record(kind, body)
    pin = blob(b'original pinned source bytes')
    configuration = record('configuration', {'id': 'configuration:history', 'operator': {'history': True}})
    profile = record('evaluation-profile', {'schema_version': '1.0.0', 'id': 'evaluation-profile:history',
        'profile_id': 'history', 'plan_source': 'static', 'router_enabled': False, 'router_version': None,
        'model_route': 'codex', 'library_snapshot_sha256': pin['sha256'], 'candidate_pins': [],
        'verifier_cc_ref': pin, 'invalid_for_product': True, 'allowed_entry_points': ['E3']})
    # Structurally valid historical provenance only. These opaque pins are not
    # admitted executable resources and this fixture grants no execution.
    source_body = {'schema_version': '1.0.0', 'id': 'original-work:history',
        'run_id': 'original-run:history', 'node_id': 'original-node', 'subnode_id': 'work',
        'attempt_id': 'original-node-a1', 'revision': 1, 'objective': 'Historical custody fixture',
        'requirement_ids': ['history'], 'node_contract_ref': pin, 'template_ref': pin,
        'checking_profile_ref': pin, 'policy_ref': pin, 'configuration_ref': configuration,
        'bindings': [{'id': 'work.binding', 'role': 'work', 'declaration_ref': pin,
            'implementation_refs': [pin], 'dependency_refs': [], 'admission_ref': pin,
            'effective_authority': {'network': 'none', 'network_allowlist': [], 'resource_reads': [pin],
                'write_roots': [], 'tools': []}, 'limits': {'time_s': 1, 'model_calls': 1, 'memory_mb': 64}}],
        'inputs': [{'name': 'input', 'contract_id': 'opaque-bytes', 'version': '1.0.0', 'required': True, 'artifact_refs': [pin]}],
        'outputs': [{'name': 'output', 'contract_id': 'opaque-bytes', 'version': '1.0.0', 'required': True}],
        'input_refs': [pin], 'required_outputs': ['output'], 'evidence_obligations': ['captured_output'],
        'subnode_limits': {'time_s': 1, 'model_calls': 1, 'memory_mb': 64}}
    validate('subnode-execution-contract', source_body)
    source = record('subnode-execution-contract', source_body)
    assets = record('evaluation-assets', {'schema': 'ai4r-evaluation-assets:1', 'id': 'assets:history',
        'profile_ref': profile, 'configuration_ref': configuration, 'account_id': 'account-history',
        'workspace_id': 'workspace-history', 'campaign_id': 'campaign-history', 'entries': [],
        'cases': [{'case_id': 'case-history', 'entry_point': 'E3', 'binding_ref': source, 'record_gate': False}]})
    public = {'request_id': 'request-history', 'case_id': 'case-history', 'campaign_id': 'campaign-history',
        'evaluation_profile_id': 'history', 'capsule_id': 'screening', 'capsule_version': '1',
        'capsule_declaration_sha256': pin['sha256'], 'binding': {'path': 'binding.json', 'sha256': source['sha256']},
        'inputs': [], 'model_route': 'codex'}
    original = blob(b'  ' + json.dumps(public, indent=2).encode('utf-8') + b'\n')
    normalized = blob(json_bytes(public))
    fingerprint = hashlib.sha256(json_bytes(['E3', public])).hexdigest()
    limits = {'time_s': 1, 'model_calls': 1, 'memory_mb': 64}
    runtime = record('evaluation-runtime', {'schema': 'ai4r-evaluation-runtime:1', 'id': 'runtime:history',
        'account_id': 'account-history', 'workspace_id': 'workspace-history', 'campaign_id': 'campaign-history',
        'profile_ref': profile, 'assets_ref': assets, 'configuration_ref': configuration,
        'model_selection_profile_ref': pin, 'deployment_ref': pin, 'policy_ref': pin,
        'library_snapshot_ref': pin, 'schedule_ref': pin, 'slots': [{'slot_id': 'slot-history',
            'request_id': public['request_id'], 'entry_point': 'E3', 'case_id': public['case_id'],
            'config_id': 'fixed', 'repeat_index': 0, 'request_sha256': fingerprint, 'limits': limits}],
        'accepted': False, 'invalid_for_product': True})
    request = record('evaluation-request', {'schema': 'ai4r-evaluation-request:1', 'id': 'request:history',
        'runtime_ref': runtime, 'slot_id': 'slot-history', 'request_id': public['request_id'], 'entry_point': 'E3',
        'case_id': public['case_id'], 'original_request_ref': original, 'normalized_request_ref': normalized,
        'fingerprint': fingerprint, 'started_unix_ns': 1, 'deadline_unix_ns': 1000000001, 'limits': limits,
        'accepted': False, 'invalid_for_product': True})
    store.connection.executescript('''CREATE TABLE evaluation_requests (
        runtime TEXT NOT NULL, slot TEXT NOT NULL, identity TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL,
        request_ref TEXT, scope_ref TEXT, terminal_ref TEXT, state TEXT NOT NULL, boot TEXT NOT NULL,
        started_ns INTEGER NOT NULL, deadline_ns INTEGER NOT NULL, cancel_id TEXT, head_ref TEXT,
        sequence INTEGER NOT NULL DEFAULT -1, PRIMARY KEY(runtime, slot));''')
    encode = lambda x: json_bytes(x).decode('utf-8')
    identity = encode(['account-history', 'workspace-history', 'campaign-history', profile, configuration, public['request_id']])
    with store.transaction() as db:
        db.execute('INSERT INTO evaluation_requests(runtime,slot,identity,fingerprint,request_ref,state,boot,started_ns,deadline_ns) VALUES (?,?,?,?,?,?,?,?,?)',
            (encode(runtime), 'slot-history', identity, fingerprint, encode(request), 'claimed', 'old-boot', 1, 1000000001))
    def event(kind, capture_kind=None, capture_ref=None, reason=None, request_override=None):
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        body = {'schema': 'ai4r-evaluation-event:1', 'id': 'event:history:' + str(row['sequence'] + 1),
            'request_ref': request_override or request, 'scope_ref': None, 'sequence': row['sequence'] + 1,
            'previous_event_ref': json.loads(row['head_ref']) if row['head_ref'] else None, 'kind': kind,
            'assignment_grant_ref': None, 'capture_kind': capture_kind, 'capture_ref': capture_ref, 'reason': reason,
            'recorded_unix_ns': row['sequence'] + 10, 'accepted': False, 'invalid_for_product': True}
        ref = record('evaluation-event', body)
        with store.transaction() as db: db.execute('UPDATE evaluation_requests SET head_ref=?,sequence=?', (encode(ref), body['sequence']))
        return ref
    event('claimed')
    for kind, ref in [('original_request', original), ('normalized_request', normalized), ('runtime', runtime), ('source_binding', source)]:
        event('captured', kind, ref)
    actor = Principal('account-history', frozenset({'workspace-history'}), frozenset({'evaluation_profile'}), frozenset({'researcher', 'reviewer'}))
    return store, runtime, request, actor, public, event


def test_history_scope_and_json_need_no_executable_resources(tmp_path):
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    store, runtime, request, actor, public, event = historical_store(tmp_path)
    try:
        before = {name: list(store.connection.execute('SELECT * FROM ' + name)) for name in ('runs', 'attempts', 'model_calls', 'tool_calls')}
        reader = EvaluationReader(store, runtime_ref=runtime)
        scope = reader.request_scope(actor, public['request_id'])
        assert set(scope) == {'account_id', 'workspace_id', 'campaign_id', 'profile_ref', 'profile_id', 'configuration_ref', 'runtime_ref', 'assets_ref'}
        assert scope['runtime_ref'] == runtime and scope['profile_id'] == 'history'
        assert reader.get(actor, public['request_id']) == {'request_id': public['request_id'], 'status': 'started', 'result': None, 'failure_ref': None, 'invalid_for_product': True}
        assert before == {name: list(store.connection.execute('SELECT * FROM ' + name)) for name in before}
    finally: store.close()


def test_history_zip_preserves_original_bytes_and_explicit_gap(tmp_path):
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    store, runtime, request, actor, public, event = historical_store(tmp_path)
    try:
        event('gap', capture_kind='workspace', reason='No workspace was produced before interruption')
        secret = store.put_blob(b'unrelated private account secret')
        payload = EvaluationReader(store, runtime_ref=runtime).export_bytes(actor, public['request_id'], audience='reviewer')
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            manifest = json.loads(archive.read('evaluation_export.json'))
            validate('urn:ai4r:private:evaluation-export:1', manifest)
            assert set(archive.namelist()) == {'evaluation_export.json'} | {f['path'] for f in manifest['files']}
            body = dict(manifest); ident = body.pop('id')
            assert ident.endswith(hashlib.sha256(json_bytes(body)).hexdigest())
            originals = [f for f in manifest['files'] if f['kind'] == 'original_request']
            assert len(originals) == 1
            original_ref = store.read_record(request)['original_request_ref']
            assert archive.read(originals[0]['path']) == store.read_blob(original_ref)
            assert all(f['artifact_ref'] != secret for f in manifest['files'])
            assert any(e['kind'] == 'workspace' and e['status'] == 'unavailable' and e['reason'] for e in manifest['required_evidence'])
            for item in manifest['files']:
                data = archive.read(item['path'])
                assert len(data) == item['byte_length'] and hashlib.sha256(data).hexdigest() == item['artifact_ref']['sha256']
    finally: store.close()


@pytest.mark.parametrize('fault', ['account', 'workspace', 'audience', 'runtime'])
def test_history_rejects_foreign_identity_and_audience(tmp_path, fault):
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    store, runtime, request, actor, public, event = historical_store(tmp_path)
    try:
        if fault == 'account': actor = Principal('foreign', actor.workspace_ids, actor.operations, actor.audiences)
        if fault == 'workspace': actor = Principal(actor.account_id, frozenset({'foreign'}), actor.operations, actor.audiences)
        if fault == 'audience': actor = Principal(actor.account_id, actor.workspace_ids, actor.operations, frozenset({'researcher'}))
        if fault == 'runtime':
            value = store.read_record(runtime); value['id'] += ':foreign'; runtime = store.append_record('evaluation-runtime', value)
        reader = EvaluationReader(store, runtime_ref=runtime)
        with pytest.raises(ResearchError): reader.export_bytes(actor, public['request_id'], audience='reviewer')
    finally: store.close()


@pytest.mark.parametrize('fault', ['foreign_event', 'source_kind', 'unsafe_zip', 'special_zip', 'missing_bytes'])
def test_history_rejects_unowned_or_unsafe_promised_bytes(tmp_path, fault):
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    store, runtime, request, actor, public, event = historical_store(tmp_path)
    try:
        if fault == 'foreign_event': event('captured', 'input', store.put_blob(b'foreign'), request_override=dict(request, id='foreign'))
        elif fault == 'source_kind': event('captured', 'actual_contract', store.append_record('subnode-execution-contract', {'id': 'forged-canonical'}))
        elif fault in {'unsafe_zip', 'special_zip'}:
            capture = io.BytesIO()
            with zipfile.ZipFile(capture, 'w') as archive:
                info = zipfile.ZipInfo('../escape' if fault == 'unsafe_zip' else 'link')
                if fault == 'special_zip': info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, b'unsafe')
            event('captured', 'workspace', store.put_blob(capture.getvalue(), media_type='application/zip'))
        else:
            pin = store.put_blob(b'missing promised original')
            event('captured', 'input', pin)
            store.blobs.path_for(pin['sha256']).unlink()
        with pytest.raises(ResearchError): EvaluationReader(store, runtime_ref=runtime).export_bytes(actor, public['request_id'], audience='reviewer')
    finally: store.close()
