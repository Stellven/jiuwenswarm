"""IF013 constructor/authorization controls; no calibration or kernel claim."""
import copy
import json
from importlib.resources import files
from pathlib import Path

import pytest

from jiuwenswarm.research.admission_executor import AdmissionTestProvider, prepare_admission_profile
from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


def candidate(store, *, kind='fixture', expects='pass', program=None):
    body = (program or "def execute(ctx, inputs):\n    if inputs['sample']['time_s'] <= 0: ctx.fail('bad_fixture')\n    return {'result': inputs['sample']}\n").encode()
    fixture = {'sample': {'time_s': 1 if expects == 'pass' else 0, 'model_calls': 0, 'memory_mb': 1}}
    test_bytes = json.dumps(fixture).encode() if kind == 'fixture' else (
        "def run(invoke):\n    result = invoke(" + repr(fixture) + ")\n    assert result['end_state'] == " + repr(expects) + "\n    return result\n").encode()
    bodies = {'candidate.py': store.put_blob(body), 'test.json' if kind == 'fixture' else 'test.py': store.put_blob(test_bytes)}
    declaration = json.loads(files('jiuwenswarm.research_assets').joinpath('compiler/intent.declaration.json').read_text(encoding='utf-8'))
    declaration['identity'].update(name='test.admission_pure', kind='tool', version_label='1',
        carrier={'ref': 'candidate.py', 'sha256': bodies['candidate.py']['sha256']},
        body=[{'path': p, 'sha256': r['sha256']} for p, r in bodies.items()])
    declaration['needs'].update(external=[], injects=[], resources=[])
    declaration['changes'].update(effect_class='pure', effects=[])
    declaration['budget']['per_call']['wall_s'] = 15
    for direction, name in [('inputs', 'sample'), ('outputs', 'result')]:
        declaration['ports'][direction] = [{'name': name, 'artifact_type': 'test_limits', 'required': True,
            'schema_ref': 'Limits', 'description': 'Controlled pure data', 'check_ids': []}]
    test = {'id': 'source_test', 'kind': kind, 'ref': {'ref': 'test.json' if kind == 'fixture' else 'test.py',
            'sha256': bodies['test.json' if kind == 'fixture' else 'test.py']['sha256']}, 'expects': expects}
    declaration['guarantees'].update(self_tests=[test], failure_modes=[{'reason_code': 'bad_fixture', 'when': 'Nonpositive fixture wall data', 'retriable': False}])
    ref = store.put_record('capsule-declaration', declaration)
    return ref, bodies, test


def provider_fixture(tmp_path, *, kind='fixture'):
    store = SQLiteRunStore(tmp_path)
    declaration, bodies, test = candidate(store, kind=kind)
    configuration = store.put_blob(b'explicit protected admission configuration')
    profile = prepare_admission_profile(store, configuration_ref=configuration,
        carrier_refs=[bodies['candidate.py']], limits={'time_s': 10, 'memory_mb': 128, 'pids_max': 32})
    actor = Principal('operator', operations=frozenset({'library_admit'}))
    provider = AdmissionTestProvider(store, configuration_ref=configuration, execution_profile_ref=profile, rpc=None)
    return store, provider, actor, declaration, bodies, test


@pytest.mark.parametrize('kind', ['command', 'fixture'])
def test_job_authority_is_durable_exact_and_clamped_before_effects(tmp_path, kind):
    store, provider, actor, declaration, bodies, test = provider_fixture(tmp_path, kind=kind)
    try:
        job = provider.issue(test, declaration, bodies, actor=actor, memory_mb=64)
        reopened = AdmissionTestProvider(store, configuration_ref=provider.configuration_ref,
            execution_profile_ref=provider.profile_ref, rpc=None)
        actual = reopened.authorize(job)
        assert actual['limits'] == {'time_s': 10, 'memory_mb': 64, 'pids_max': 32}
        request = store.read_record(actual['admission_request_ref'])
        assert request['admission_memory_mb'] == 64 and request['actor_id'] == 'operator'
        assert actual['declaration_ref'] == declaration and actual['body_refs'] == bodies
        assert not list(store.iter_records(kinds=('library-admission', 'gate-decision', 'model-call-start')))
    finally:
        store.close()


@pytest.mark.parametrize('fault', ['memory', 'body', 'test', 'configuration', 'expiry'])
def test_changed_job_cannot_borrow_the_admission_request(tmp_path, fault):
    store, provider, actor, declaration, bodies, test = provider_fixture(tmp_path)
    try:
        original = provider.issue(test, declaration, bodies, actor=actor, memory_mb=64)
        job = store.read_record(original)
        if fault == 'memory': job['limits']['memory_mb'] = 65
        elif fault == 'body': job['body_refs']['candidate.py'] = bodies['test.json']
        elif fault == 'test': job['test_id'] = 'foreign'
        elif fault == 'configuration': job['configuration_ref'] = bodies['test.json']
        else: job['expires_at'] = '2000-01-01T00:00:00Z'
        changed = store.append_record('admission-self-test-job', job | {'id': job['id'] + ':changed'})
        with pytest.raises(ResearchError): provider.authorize(changed)
    finally:
        store.close()


def test_ordinary_actor_cannot_issue_candidate_authority(tmp_path):
    store, provider, _, declaration, bodies, test = provider_fixture(tmp_path)
    try:
        with pytest.raises(ResearchError):
            provider.issue(test, declaration, bodies, actor=Principal('ordinary'), memory_mb=64)
        assert not list(store.iter_records(kinds=('admission-self-test-request', 'admission-self-test-job')))
    finally:
        store.close()


def test_unbuilt_model_adapter_does_not_issue_or_borrow_authority(tmp_path):
    store, provider, actor, declaration, bodies, test = provider_fixture(tmp_path)
    try:
        value = store.read_record(declaration)
        value['needs']['injects'] = [{'service_key': 'audited_model_bridge', 'interface_version_range': '1.x'}]
        changed = store.put_blob(json.dumps(value).encode())
        with pytest.raises(ResearchError, match='self_test_adapter_unbuilt'):
            provider.issue(test, changed, bodies, actor=actor, memory_mb=64)
        assert not list(store.iter_records(kinds=('admission-self-test-request','admission-self-test-job','model-call-start')))
    finally:
        store.close()


@pytest.mark.asyncio
async def test_executor_client_sends_only_original_job_ref_without_retry():
    from jiuwenswarm.research.executor_rpc import ExecutorClient
    calls = []
    ref = {'id': 'protected-job', 'sha256': 'a'*64}
    class RPC:
        async def call(self, operation, payload, **kwargs):
            calls.append((operation,payload,kwargs))
            raise RuntimeError('delivery may have occurred')
    with pytest.raises(RuntimeError):
        await ExecutorClient(RPC()).run_admission_self_test(ref)
    assert calls == [('run_admission_self_test', {'job_ref':ref}, {'timeout_s':3600})]


@pytest.mark.asyncio
@pytest.mark.parametrize('code',['ENVIRONMENT_BLOCKED','AUDIT_UNAVAILABLE','DELIVERY_UNKNOWN'])
async def test_finite_transport_unavailable_is_blocked_without_retry_or_candidate_rejection(tmp_path,code):
    from jiuwenswarm.research.bridge import BridgeError
    store,provider,actor,declaration,bodies,test=provider_fixture(tmp_path)
    calls=[]
    class RPC:
        async def run_admission_self_test(self,ref):
            calls.append(ref);raise BridgeError(code)
    provider.rpc=RPC()
    try:
        with pytest.raises(ResearchError,match='self_test_unavailable') as caught:
            await provider.for_admission(actor,64)(test,declaration,bodies)
        assert caught.value.details['transport_code']==code and len(calls)==1
        assert not list(store.iter_records(kinds=('admission-self-test-result','library-admission')))
    finally:store.close()


@pytest.mark.asyncio
async def test_unavailable_kernel_is_environment_blocked_before_child_effects(tmp_path):
    from jiuwenswarm.research.admission_executor import AdmissionExecutor
    from jiuwenswarm.research.executor import RestrictedExecutor
    from jiuwenswarm.research.executor_rpc import ClaimLedger
    store,provider,actor,declaration,bodies,test=provider_fixture(tmp_path/'state')
    ledger=ClaimLedger(tmp_path/'ledger')
    kernel=RestrictedExecutor(workspace_root=tmp_path,cgroup_root=None,authorize_job=lambda _:None,capture=store.put_blob)
    producer=AdmissionExecutor(store,kernel,authorize=provider.authorize,ledger=ledger,staging_root=tmp_path/'jobs')
    try:
        job=provider.issue(test,declaration,bodies,actor=actor,memory_mb=64)
        with pytest.raises(ResearchError) as caught:await producer.run(job)
        assert caught.value.code=='ENVIRONMENT_BLOCKED' and kernel.active=={}
        assert not list(store.iter_records(kinds=('admission-self-test-execution','admission-self-test-result')))
    finally:ledger.close();store.close()
