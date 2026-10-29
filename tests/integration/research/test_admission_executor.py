"""Actual IF013 pure Python driver/candidate kernel population, never calibration."""
import importlib.util
import asyncio
import json
import os
import tempfile
import uuid
from pathlib import Path

import pytest

from jiuwenswarm.research.admission_executor import AdmissionExecutor, AdmissionTestProvider, prepare_admission_profile
from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.executor import RestrictedExecutor
from jiuwenswarm.research.executor_rpc import ClaimLedger
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes

_spec = importlib.util.spec_from_file_location('admission_authoring_fixture', Path(__file__).parents[2] / 'unit_tests/research/test_admission_executor.py')
_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixtures)


@pytest.fixture
def admission_kernel():
    delegation = os.environ.get('AI4R_EXECUTOR_CGROUP_ROOT')
    if not delegation:
        pytest.fail('Actual owned cgroup delegation is required; no required skip')
    root = Path(tempfile.mkdtemp(prefix='ai4r-adm-')); root.chmod(0o711)
    store = SQLiteRunStore(root / 'store')
    kernel = RestrictedExecutor(workspace_root=root, cgroup_root=delegation,
        authorize_job=lambda job: (_ for _ in ()).throw(RuntimeError('No ordinary admitted grant')),
        capture=store.put_blob)
    assert kernel.prerequisites() == []
    ledger = ClaimLedger(root / 'ledger')
    yield root, store, kernel, ledger
    try:
        evidence = Path('/evidence') / ('captures-' + uuid.uuid4().hex)
        evidence.mkdir()
        records = list(store.iter_records())
        (evidence / 'records.json').write_bytes(json_bytes(records))
        refs = store.ref_index()
        (evidence / 'refs.json').write_bytes(json_bytes(refs))
        for identifier, metadata in refs.items():
            ref = {'id': identifier, 'sha256': metadata['sha256']}
            (evidence / ref['sha256']).write_bytes(store.read_blob(ref))
    finally:
        try:
            for observation in kernel.owned_groups.values():
                group = observation['path']
                if group.exists():
                    assert group.parent == Path(delegation) and group.stat().st_ino == observation['inode']
                    assert not (group / 'cgroup.procs').read_text().strip()
                    group.rmdir()
        finally:
            ledger.close(); store.close()


def assembled(fixture, *, kind='fixture', expects='pass', program=None, command=None, time_s=10):
    root, store, kernel, ledger = fixture
    declaration, bodies, test = _fixtures.candidate(store, kind=kind, expects=expects, program=program)
    if command is not None:
        value = store.read_record(declaration)
        body = store.put_blob(command)
        bodies['test.py'] = body
        for pin in value['identity']['body']:
            if pin['path'] == 'test.py': pin['sha256'] = body['sha256']
        value['guarantees']['self_tests'][0]['ref']['sha256'] = body['sha256']
        declaration = store.put_record('capsule-declaration', value)
        test = value['guarantees']['self_tests'][0]
    config = store.put_blob(b'Actual kernel pure-adapter test configuration')
    profile = prepare_admission_profile(store, configuration_ref=config, carrier_refs=[bodies['candidate.py']],
        limits={'time_s': time_s, 'memory_mb': 64, 'pids_max': 32})
    provider = AdmissionTestProvider(store, configuration_ref=config, execution_profile_ref=profile, rpc=None)
    job = provider.issue(test, declaration, bodies, actor=Principal('operator', operations=frozenset({'library_admit'})), memory_mb=64)
    producer = AdmissionExecutor(store, kernel, authorize=provider.authorize, ledger=ledger, staging_root=root / 'a')
    return store, producer, job


@pytest.mark.asyncio
@pytest.mark.parametrize('kind,expects', [('command','pass'), ('fixture','pass'), ('command','bad_fixture'), ('fixture','bad_fixture')])
async def test_actual_candidate_and_driver_captures_join_original_job(admission_kernel, kind, expects):
    store, producer, job_ref = assembled(admission_kernel, kind=kind, expects=expects)
    result_ref = await producer.run(job_ref)
    result = store.read_record(result_ref)
    assert store.record_kind(result_ref) == 'admission-self-test-result'
    assert result['job_ref'] == job_ref and result['end_state'] == expects
    assert result['reason_code'] == (None if expects == 'pass' else expects)
    assert bool(result['output_refs']) == (expects == 'pass')
    assert len(result['candidate_execution_refs']) == 1 and result['model_call_refs'] == []
    child = store.read_record(result['candidate_execution_refs'][0])
    driver = store.read_record(result['driver_execution_ref'])
    candidate = store.read_record(child['execution_receipt_ref'])
    assert driver['job_id'] != candidate['job_id']
    for receipt in [driver, candidate]:
        assert receipt['contract_ref'] == job_ref and receipt['termination_reason'] == 'completed'
        proof = json.loads(store.read_blob(receipt['observed_limits']['isolation_probe_ref']))
        assert proof['ready'] and proof['executor_uid'] == proof['executor_gid'] == 10002
        assert proof['cap_effective'] == '0000000000000000' and proof['no_new_privileges'] == '1'
        assert proof['network'] == 'none' and all(proof['denied_paths'].values())
        assert receipt['observed_limits']['memory_max'] == str(64 * 1024 * 1024)
    stdout = json.loads(store.read_blob(driver['stdout_ref']))
    assert stdout['candidate_call_id'] == child['id']
    assert stdout['outputs'] == {name: json.loads(store.read_blob(ref)) for name,ref in child['output_refs'].items()}
    before = len(list(store.iter_records()))
    assert await producer.run(job_ref) == result_ref
    assert len(list(store.iter_records())) == before
    assert not list(store.iter_records(kinds=('library-admission', 'model-call-start', 'gate-decision')))
    from jiuwenswarm.research.checks.admission import verify_self_test
    job = store.read_record(job_ref)
    declaration = store.read_record(job['declaration_ref'])
    test = declaration['guarantees']['self_tests'][0]
    verify_self_test(store, test, job['declaration_ref'], job['body_refs'], result_ref,
        memory_mb=64, actor=Principal('operator'), configuration_ref=job['configuration_ref'],
        execution_profile_ref=job['execution_profile_ref'])


@pytest.mark.asyncio
async def test_printing_pass_without_actual_candidate_cannot_qualify(admission_kernel):
    command = b"def run(invoke):\n    return {'end_state':'pass','outputs':{},'reason_code':None,'candidate_call_id':'invented'}\n"
    store, producer, job_ref = assembled(admission_kernel, kind='command', command=command)
    with pytest.raises(ResearchError, match='did not invoke'):
        await producer.run(job_ref)
    assert not list(store.iter_records(kinds=('admission-self-test-result', 'admission-self-test-candidate-execution')))
    assert len(list(store.iter_records(kinds=('admission-self-test-failure',)))) == 1


@pytest.mark.asyncio
async def test_actual_candidate_cannot_read_driver_capability_or_protected_store(admission_kernel):
    program = """from pathlib import Path
def execute(ctx, inputs):
    for name in ['/resources/invoke.sock', '/run/ai4r', '/var/lib/ai4r', '/resources/input/driver-input/manifest.json']:
        assert not Path(name).exists(), name
    return {'result': inputs['sample']}
"""
    store, producer, job_ref = assembled(admission_kernel, program=program)
    result = store.read_record(await producer.run(job_ref))
    assert result['end_state'] == 'pass'


@pytest.mark.asyncio
@pytest.mark.parametrize('interruption', ['timeout', 'cancel'])
async def test_actual_interruption_retains_raw_receipts_and_contains_both_children(admission_kernel, interruption):
    from jiuwenswarm.research.bridge import BridgeError
    program = "import time\ndef execute(ctx, inputs):\n    time.sleep(60)\n    return {'result': inputs['sample']}\n"
    store, producer, job_ref = assembled(admission_kernel, program=program, time_s=2 if interruption == 'timeout' else 10)
    task = asyncio.create_task(producer.run(job_ref))
    kernel = admission_kernel[2]
    if interruption == 'cancel':
        async with asyncio.timeout(5):
            while len(kernel.active) < 2:
                await asyncio.sleep(.01)
        task.cancel()
    with pytest.raises((ResearchError, asyncio.CancelledError)):
        await task
    assert kernel.active == {}
    receipts = [row['record'] for row in store.iter_records(kinds=('admission-self-test-execution',))]
    assert receipts and any(r['termination_reason'] in {'timeout','cancelled'} for r in receipts)
    for receipt in receipts:
        store.read_blob(receipt['stdout_ref']); store.read_blob(receipt['stderr_ref'])
    assert not list(store.iter_records(kinds=('admission-self-test-result',)))
    assert list(store.iter_records(kinds=('admission-self-test-failure',)))
    # The duplicate cannot dispatch a second driver/candidate after a possible effect.
    before = len(kernel.owned_groups)
    with pytest.raises((ResearchError, BridgeError)):
        await producer.run(job_ref)
    assert len(kernel.owned_groups) == before


@pytest.mark.asyncio
async def test_driver_cannot_invoke_second_candidate_or_forge_result(admission_kernel):
    command = b"def run(invoke):\n    values={'sample':{'time_s':1,'memory_mb':1,'model_calls':0}}\n    invoke(values)\n    return invoke(values)\n"
    store, producer, job_ref = assembled(admission_kernel, kind='command', command=command)
    with pytest.raises(ResearchError):
        await producer.run(job_ref)
    assert len(list(store.iter_records(kinds=('admission-self-test-candidate-execution',)))) == 1
    assert not list(store.iter_records(kinds=('admission-self-test-result',)))


@pytest.mark.asyncio
async def test_actual_library_runs_every_author_test_through_private_rpc_and_keeps_independent_checks(admission_kernel):
    """Real Library/IPC/kernel consumer; missing calibration remains blocked."""
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research.executor_rpc import ExecutorClient
    from jiuwenswarm.research.private_rpc import PrivateRPCClient,PrivateRPCServer
    root,store,kernel,ledger=admission_kernel
    declaration_ref,bodies,first=_fixtures.candidate(store)
    declaration=store.read_record(declaration_ref)
    negative=store.put_blob(json_bytes({'sample':{'time_s':0,'memory_mb':1,'model_calls':0}}))
    bodies['negative.json']=negative
    declaration['identity']['body'].append({'path':'negative.json','sha256':negative['sha256']})
    declaration['guarantees']['self_tests'].append({'id':'negative_test','kind':'fixture',
        'ref':{'ref':'negative.json','sha256':negative['sha256']},'expects':'bad_fixture'})
    declaration_ref=store.put_record('capsule-declaration',declaration)
    configuration=store.put_blob(b'Explicit connected admission test configuration')
    profile=prepare_admission_profile(store,configuration_ref=configuration,carrier_refs=[bodies['candidate.py']],
        limits={'time_s':10,'memory_mb':64,'pids_max':32})
    provider=AdmissionTestProvider(store,configuration_ref=configuration,execution_profile_ref=profile,rpc=None)
    producer=AdmissionExecutor(store,kernel,authorize=provider.authorize,ledger=ledger,staging_root=root/'a')
    async def run(payload):
        assert set(payload)=={'job_ref'}
        return await producer.run(payload['job_ref'])
    session={'session_id':'owned-admission-component','capability':uuid.uuid4().hex}
    server=await PrivateRPCServer(root/'broker'/'admission.sock',protocol='owned-admission-component:1',
        handlers={'run_admission_self_test':run},allowed_uids={os.geteuid()},**session).start()
    provider.rpc=ExecutorClient(PrivateRPCClient(server.path,protocol='owned-admission-component:1',peer_uid=os.geteuid(),**session))
    library=LibraryService(store,self_test_provider=provider)
    try:
        actor=Principal('operator',operations=frozenset({'library_admit'}))
        result=store.read_record(await library.admit(declaration_ref,bodies,actor,memory_mb=64))
        proofs=list(store.iter_records(kinds=('admission-self-test-result',)))
        assert {row['record']['end_state'] for row in proofs}=={'pass','bad_fixture'} and len(proofs)==2
        assert len(list(store.iter_records(kinds=('admission-self-test',))))==2
        assert result['status']=='blocked' and result['standing']=='inactive'
        assert library.entries()==[] and not list(store.iter_records(kinds=('activation-record','model-call','gate-decision')))
        for row in store.iter_records(kinds=('admission-self-test-request',)):
            assert row['record']['actor_id']=='operator' and row['record']['admission_memory_mb']==64
    finally:await server.close()
