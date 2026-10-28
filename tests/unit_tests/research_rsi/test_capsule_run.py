"""Pinned runner configuration and public evaluator pipe interoperability."""
import asyncio
import base64
import copy
import hashlib
import io
import json
from types import SimpleNamespace
import pytest

from deploy.m1 import rsi_capsule_run as run
from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.targets.capsules import public_fixtures
from jiuwenswarm.research_rsi.targets.capsule_runtime import capsule_worker_program, BOOTSTRAP_SCHEMA
from tests.unit_tests.research_rsi.test_capsule_session import fixture, FakeGoverned


def test_readonly_relay_guard_accepts_exact_idle_status_with_private_fixed_child(tmp_path,monkeypatch):
    helper=tmp_path/'fixed.py';helper.write_bytes(b'fixed composition')
    pin=hashlib.sha256(helper.read_bytes()).hexdigest()
    monkeypatch.setattr(run,'COMPOSITION_SHA256',pin)
    monkeypatch.setattr(run,'protected',lambda path,**kwargs: __import__('pathlib').Path(path))
    fact={'binding_sha256':'a'*64,'policy_sha256':'b'*64,'status_sha256':'c'*64,'active':False,'unresolved':False}
    calls=[]
    def child(argv,**kwargs):
        calls.append((argv,kwargs));return SimpleNamespace(returncode=0,stdout=encoded(fact))
    monkeypatch.setattr(run.subprocess,'run',child)
    value={'composition_path':str(helper),'composition_sha256':pin,'composition':{'account_root':'/private/existing-account'}}
    assert run.readonly_relay_fact(value)==fact
    argv,kwargs=calls[0]
    assert argv[1:4]==['-I','-B','-c']
    assert kwargs['user']==kwargs['group']==12001 and kwargs['extra_groups']==[13000]
    assert kwargs['timeout']==15 and kwargs['close_fds'] is True
    assert 'PYTHONPATH' not in kwargs['env']
    assert "helper.relay_idle_fact" in argv[4] and "'/opt/ai4r-rsi-frozen-v18-03ed3199'" in argv[4]


@pytest.mark.parametrize('outcome',[None,{'active':True,'unresolved':False},{'active':False,'unresolved':True}])
def test_readonly_relay_guard_blocks_unavailable_busy_or_unresolved(tmp_path,monkeypatch,outcome):
    helper=tmp_path/'fixed.py';helper.write_bytes(b'fixed composition')
    pin=hashlib.sha256(helper.read_bytes()).hexdigest()
    monkeypatch.setattr(run,'COMPOSITION_SHA256',pin)
    monkeypatch.setattr(run,'protected',lambda path,**kwargs: __import__('pathlib').Path(path))
    fact={'binding_sha256':'a'*64,'policy_sha256':'b'*64,'status_sha256':'c'*64,'active':False,'unresolved':False}
    if outcome is not None:fact.update(outcome)
    monkeypatch.setattr(run.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=1 if outcome is None else 0,stdout=encoded(fact)))
    with pytest.raises(ValueError,match='RELAY_STATUS_UNAVAILABLE|CLOSED_IDLE_NATIVE_RELAY_REQUIRED'):
        run.readonly_relay_fact({'composition_path':str(helper),'composition_sha256':pin,'composition':{'account_root':'/private/existing-account'}})


def test_controller_compose_failure_retains_known_pre_session_phase(tmp_path):
    store,session,runtime,_=fixture(tmp_path,'utility.calculate')
    progress={'phase':'WAITING_FOR_EVALUATOR'}
    async def unavailable(value,evaluate):raise FileNotFoundError('Actual missing composition carrier')
    helper=SimpleNamespace(compose=unavailable)
    try:
        with pytest.raises(FileNotFoundError):
            asyncio.run(run.controller({'session':session,'composition':{}},io.BytesIO(),io.BytesIO(),helper,progress=progress))
        assert progress['phase']=='COMPOSING'
        assert store.db.execute("SELECT name FROM sqlite_master WHERE name='capsule_session_claims'").fetchone() is None
    finally:store.close()


def test_public_capture_closure_transfers_actual_bytes_and_skips_external_worker_pins(tmp_path):
    store = RecordStore(tmp_path / 'root')
    try:
        raw = store.put_bytes(b'actual stdout')
        nested = store.put({'stdout_ref': raw, 'worker_ref': {'id': 'external', 'sha256': 'a'*64}})
        values = list(run.capture_closure(store, {'result_ref': nested, 'duplicate': raw}))
        assert {item['ref']['id'] for item in values} == {raw['id'], nested['id']}
        assert all(hashlib.sha256(base64.b64decode(item['bytes_base64'])).hexdigest() == item['ref']['sha256'] for item in values)
    finally:
        store.close()


@pytest.mark.parametrize('tampered_program', [False, True])
def test_controller_imports_exact_root_rows_and_runs_once_only_governed_handles(tmp_path, tampered_program):
    store, session, runtime, _ = fixture(tmp_path, 'utility.calculate')
    root = RecordStore(tmp_path / 'root-captures')
    try:
        session['grant'].update(iterations=1, limits={'wall_s': 60}, expires_unix_s=int(__import__('time').time())+60)
        session['grant_ref'] = store.put(session['grant'])
        changed = b'# changed public carrier\n'
        changed_ref = store.put_bytes(changed)
        root.put_ref(session['grant_ref'], encoded(session['grant']))
        frames = []
        for role, candidate_ref in [('parent', session['parent_body_ref']), ('candidate', changed_ref)]:
            rows = []
            for index, fixture_row in enumerate(public_fixtures('utility.calculate')):
                input_ref = root.put({'packet': fixture_row['packet']})
                program = capsule_worker_program('utility.calculate', manifest_sha256='a'*64,
                    candidate_sha256=candidate_ref['sha256'], input_sha256=input_ref['sha256'])
                program_ref = root.put_bytes(b'tampered' if tampered_program else program)
                row = {'fixture_id': fixture_row['id'], 'candidate_ref': candidate_ref, 'group_empty': True,
                    'runtime_manifest_sha256': 'a'*64, 'receipt': {'subject_ref': candidate_ref},
                    'task_success': True, 'protected_wall_s': .1, 'input_ref': input_ref,
                    'program_ref': program_ref, 'bootstrap_schema': BOOTSTRAP_SCHEMA}
                rows.append({**row, 'evidence_ref': root.put(row)})
            result = {'schema': 'ai4r-rsi-whole-capsule-visible-result:1', 'role': role,
                'executions': len(rows), 'passed_count': len(rows), 'passed': True,
                'grant_ref': session['grant_ref'], 'security': 'UNQUALIFIED', 'model_calls': 0,
                'rows': rows, 'protected_wall_s': sum(row['protected_wall_s'] for row in rows)}
            result['result_ref'] = root.put(result)
            frames.extend({'capture': capture} for capture in run.capture_closure(root, result))
            frames.append({'evaluation': result})
        incoming = io.BytesIO(b''.join(encoded(frame)+b'\n' for frame in frames))
        outgoing = io.BytesIO()
        handles = []
        def factory(resources, lease, contract_ref, run_id):
            model = FakeGoverned(store, 'diagnosis' if contract_ref == session['diagnosis_contract_ref'] else 'proposal')
            handles.append(model)
            return model
        async def compose(value, evaluate):
            runtime.evaluate = evaluate
            runtime.resources = None; runtime.lease = None
            runtime.records = SimpleNamespace(put_ref=store.put_ref, close=lambda: None)
            runtime.lease_records = SimpleNamespace(close=lambda: None)
            runtime.core = SimpleNamespace(close=lambda: None)
            runtime.subscription = SimpleNamespace(transport=SimpleNamespace())
            return runtime
        helper = SimpleNamespace(compose=compose, DevelopmentModel=factory,
            read_frame_deadline=lambda stream, deadline: json.loads(stream.readline()),
            write_frame=lambda stream, value: stream.write(encoded(value)+b'\n'))
        value = {'session': session, 'composition': {}}
        result = asyncio.run(run.controller(value, incoming, outgoing, helper))
        requests = [json.loads(row) for row in outgoing.getvalue().splitlines()]
        if tampered_program:
            assert result['status'] == 'ERROR_NO_REPLAY'
            assert [request['role'] for request in requests] == ['parent']
            assert not any(handle.used for handle in handles)
        else:
            assert result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED'
            assert result['model_calls'] == 2
            assert [request['role'] for request in requests] == ['parent', 'candidate']
            assert requests[1]['binding']['candidate_ref'] == changed_ref
            assert store.get(result['parent_visible']['result_ref'])['role'] == 'parent'
    finally:
        store.close(); root.close()
