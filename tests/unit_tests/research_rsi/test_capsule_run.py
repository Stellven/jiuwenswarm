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
def test_controller_imports_exact_root_rows_and_runs_once_only_governed_handles(tmp_path, tampered_program, monkeypatch):
    store, session, runtime, _ = fixture(tmp_path, 'utility.calculate')
    # In-memory frames; the select()-based reader needs a real descriptor.
    monkeypatch.setattr(run, 'read_frame_deadline', lambda stream, deadline: (
        lambda raw: json.loads(raw) if raw else None)(stream.readline()))
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
            assert 'EXACT_GUARDED_BOOTSTRAP_PROGRAM_REQUIRED' in store.get(result['failure_ref'])['message']
        else:
            assert result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED', store.get(result['failure_ref'])
            assert result['model_calls'] == 2
            assert [request['role'] for request in requests] == ['parent', 'candidate']
            assert [(r['iteration'], r['trials']) for r in requests] == [(0, 1), (1, 1)]
            assert requests[1]['binding']['candidate_ref'] == changed_ref
            assert store.get(result['parent_visible']['result_ref'])['role'] == 'parent'
    finally:
        store.close(); root.close()


class FakeRootDispatcher:
    """Interface A Root dispatcher stand-in: real captures, no sandbox."""
    fail_at_iteration = None

    def __init__(self, *, root, runtime_root, manifest, grant_path, grant_sha256, cgroup_root, captures):
        self.captures, self.grant = captures, FakeRootDispatcher.grant
        self.grant_ref = FakeRootDispatcher.grant_ref
        self.executions, self.halted, self.completed = 0, False, {}
        self.deadline = __import__('time').monotonic() + 60
        self.calls = []

    def plan(self):
        return {'maximum_executions': 1000, 'grant_sha256': 'g' * 64, 'bootstrap_schema': BOOTSTRAP_SCHEMA}

    async def evaluate(self, role, *, body, candidate_ref, binding=None, iteration=0, trials=1):
        from tests.unit_tests.research_rsi.test_capsule_loop import HELD_OUT, parse
        if iteration == self.fail_at_iteration:
            self.halted = True
            raise ValueError('SYNTHETIC_ROOT_REFUSAL')
        name = self.grant['capsule_name']
        self.captures.put_ref(candidate_ref, body)
        behaviour = parse(body)
        rows = []
        for fixture_set, fixtures in (('public', public_fixtures(name)), ('held_out', HELD_OUT)):
            for row in fixtures:
                input_ref = self.captures.put({'packet': row.get('packet', row['id'])})
                program = capsule_worker_program(name, manifest_sha256=self.grant['runtime_manifest_sha256'],
                    candidate_sha256=candidate_ref['sha256'], input_sha256=input_ref['sha256'],
                    iterations=self.grant['iterations'])
                item = {'fixture_id': row['id'], 'fixture_set': fixture_set,
                        'task_success': row['id'] not in behaviour['fail'], 'protected_wall_s': behaviour['wall'],
                        'output_bytes': 3, 'checks': {}, 'receipt': {'subject_ref': candidate_ref},
                        'candidate_ref': candidate_ref, 'input_ref': input_ref,
                        'program_ref': self.captures.put_bytes(program), 'bootstrap_schema': BOOTSTRAP_SCHEMA}
                rows.append({**item, 'evidence_ref': self.captures.put(item)})
        total = sum(row['protected_wall_s'] for row in rows)
        result = {'schema': 'ai4r-rsi-whole-capsule-visible-result:2', 'role': role, 'iteration': iteration,
            'subject_sha256': candidate_ref['sha256'], 'passed_count': sum(r['task_success'] for r in rows),
            'case_count': len(rows), 'protected_wall_s': total,
            'trial_wall_s': [total * (1 + 0.01 * (i % 3 - 1)) for i in range(trials)] if trials > 1 else [],
            'rows': rows, 'executions': len(rows) * trials, 'failure': None, 'grant_ref': self.grant_ref,
            'security': 'UNQUALIFIED', 'model_calls': 0}
        self.executions += result['executions']
        self.completed.setdefault(role, []).append(iteration)
        return {**result, 'result_ref': self.captures.put(result)}


@pytest.mark.parametrize('fail_at', [None, 2])
def test_pipe_protocol_serves_n_evaluations_over_real_pipes(tmp_path, monkeypatch, fail_at):
    import os, threading, time
    from jiuwenswarm.research_rsi.targets import capsule_executor
    from tests.unit_tests.research_rsi.test_capsule_loop import make_session, spec, diagnosis_text, proposal_text
    loop = {'model_backend': {'kind': 'host-codex'}, 'max_iterations': 3, 'max_no_progress': 3, 'trials': 3}
    store, session, runtime, _ = make_session(tmp_path, loop=loop, extra_contracts=2)
    session['grant'].update(iterations=1, limits={'wall_s': 60}, expires_unix_s=int(time.time()) + 60)
    session['grant_ref'] = store.put(session['grant'])
    FakeRootDispatcher.grant, FakeRootDispatcher.grant_ref = session['grant'], session['grant_ref']
    monkeypatch.setattr(FakeRootDispatcher, 'fail_at_iteration', fail_at)
    monkeypatch.setattr(capsule_executor, 'WholeCapsuleDispatcher', FakeRootDispatcher)
    case = public_fixtures('utility.calculate')[0]['id']
    bodies = iter([spec(wall=0.05), spec(fail=[case]), spec(wall=0.04)])

    class Handle:
        def __init__(self):
            self.used, self.last_model_calls, self.last_evidence, self.last_generating_model = False, None, [], 'host'

        async def __call__(self, prompt):
            self.used, self.last_model_calls = True, 1
            self.last_evidence = [store.put({'call': prompt[:20]})]
            if 'visible_evidence' in json.loads(prompt):
                return diagnosis_text(prompt)
            return proposal_text(next(bodies), 'pipe')(prompt)

    def write_frame(stream, value):
        stream.write(encoded(value) + b'\n'); stream.flush()

    def exclusive(path, value):
        with open(path, 'xb') as stream:
            stream.write(encoded(value))
    root = tmp_path / 'root'; root.mkdir()
    value = {'session': session, 'composition': {},
             'evaluator': {'root': str(root), 'metadata': {}, 'runtime_root': None, 'manifest': None,
                           'grant_path': None, 'grant_sha256': None, 'cgroup_root': None}}
    request_read, request_write = os.pipe(); response_read, response_write = os.pipe()
    outcome = {}

    def serve():
        try:
            with os.fdopen(request_read, 'rb') as incoming, os.fdopen(response_write, 'wb') as outgoing:
                asyncio.run(run.evaluator(value, incoming, outgoing, 'c' * 64,
                                          SimpleNamespace(write_frame=write_frame, exclusive=exclusive)))
        except BaseException as error:
            outcome['error'] = error
    thread = threading.Thread(target=serve); thread.start()

    async def compose(composition, evaluate):
        runtime.evaluate = evaluate
        runtime.resources = runtime.lease = None
        runtime.records = SimpleNamespace(put_ref=store.put_ref, close=lambda: None)
        runtime.lease_records = SimpleNamespace(close=lambda: None)
        runtime.core = SimpleNamespace(close=lambda: None)
        runtime.subscription = SimpleNamespace(transport=SimpleNamespace())
        return runtime
    helper = SimpleNamespace(compose=compose, DevelopmentModel=lambda *args: Handle(), write_frame=write_frame)
    try:
        with os.fdopen(response_read, 'rb') as incoming, os.fdopen(request_write, 'wb') as outgoing:
            ready = run.read_frame_deadline(incoming, time.monotonic() + 10)
            assert ready['ready'] is True and ready['plan']['maximum_executions'] == 1000
            result = asyncio.run(run.controller(value, incoming, outgoing, helper))
        thread.join(10)
        loop = result['loop']
        if fail_at is None:
            assert 'error' not in outcome and result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED'
            assert loop['stop_reason'] == 'max_iterations' and loop['completed_iterations'] == 3
            assert [row['kept'] for row in loop['iterations']] == [True, False, True] and loop['best']['iteration'] == 3
            completion = json.loads((root / 'complete.json').read_bytes())
            assert completion['stop'] == 'CONTROLLER_CLOSED'
            assert [(e['role'], e['iteration'], e['trials']) for e in completion['evaluations']] == [
                ('parent', 0, 3), ('candidate', 1, 3), ('candidate', 2, 3), ('candidate', 3, 3)]
            # every Root row and result was transferred exactly into the controller store
            for row in loop['iterations']:
                assert store.get(row['visible']['result_ref'])['iteration'] == row['iteration']
            assert result['model_calls'] == 6
        else:
            assert isinstance(outcome['error'], ValueError) and not (root / 'complete.json').exists()
            assert loop['stop_reason'] == 'error' and loop['completed_iterations'] == 2
            assert loop['iterations'][1]['outcome'] == 'error'
            assert 'SYNTHETIC_ROOT_REFUSAL' in loop['iterations'][1]['reason']
            # earlier validated evaluations are retained; run() may still publish them
            assert result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED' and loop['best']['iteration'] == 1
    finally:
        store.close()
