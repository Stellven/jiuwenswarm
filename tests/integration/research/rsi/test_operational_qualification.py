"""Actual negative boundaries; not a replacement for source RSIV-1 through13."""
import asyncio
import os
import pytest
from jiuwenswarm.research.contracts import Principal,ResearchError
from jiuwenswarm.research.library import LibraryService
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research_rsi.ports import PrivatePort,request
from jiuwenswarm.research_rsi.qualification import require_qualification


@pytest.mark.asyncio
@pytest.mark.parametrize('operation',['session_start','proposal','trial','oracle','package','admit','activate'])
async def test_actual_private_socket_cannot_turn_inspection_into_unqualified_effect(tmp_path,operation):
    assert hasattr(os,'getuid'),'BLOCKED: actual Linux peer identity required'
    effects=[];pin={'id':'captured-session-not-qualification','sha256':'a'*64}
    async def effect(ref):
        require_qualification(None,operation,session_ref=ref)
        effects.append(ref)
    async def inspect(ref):return {'state':'inspection','session_ref':ref}
    socket=tmp_path/'qualification.sock'
    server=asyncio.create_task(PrivatePort({'effect':effect,'inspect':inspect},[os.getuid()]).serve(socket))
    try:
        async with asyncio.timeout(5):
            while not socket.is_socket():await asyncio.sleep(.01)
        denied=await request(socket,os.getuid(),'effect',pin)
        assert denied['status']=='blocked' and effects==[]
        observed=await request(socket,os.getuid(),'inspect',pin)
        assert observed['status']=='ok' and observed['result']['state']=='inspection'
    finally:
        server.cancel();await asyncio.gather(server,return_exceptions=True)
        assert not socket.exists()


@pytest.mark.asyncio
async def test_actual_durable_library_blocks_unqualified_package_and_direct_lineage(tmp_path):
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    fixture=make_unit_package(tmp_path/'state');store=fixture['store'];library=LibraryService(store)
    actor=Principal('os-operator',operations=frozenset({'library_admit'}))
    try:
        with pytest.raises(ResearchError,match='qualification'):
            await library.admit_rsi(fixture['put'](fixture['package']),actor)
        with pytest.raises(ResearchError,match='qualification'):
            await library.admit(fixture['package']['child_declaration_ref'],{},actor,memory_mb=512)
        assert not library.entries()
        assert not list(store.iter_records(kinds=('admission-record','activation-record','rsi-security-authorization')))
        assert list(store.iter_records(kinds=('rsi-security-blocked',)))
    finally:store.close()
    reopened=SQLiteRunStore(tmp_path/'state')
    try:
        assert list(reopened.iter_records(kinds=('rsi-security-blocked',)))
        assert not LibraryService(reopened).entries()
    finally:reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('subject',['child','parent'])
async def test_direct_core_trial_entry_cannot_bypass_missing_current_qualification(tmp_path,subject):
    from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
    if subject=='child':
        from tests.unit_tests.research.test_isolated_evaluation import trial_fixture
        store,owner,fixture,binding=await trial_fixture(tmp_path)
        prepare=owner.prepare_isolated_evaluation;execute=owner.execute_isolated_evaluation
        kinds=('isolated-reservation-claim','isolated-evaluation-trial','model-call-start')
    else:
        from tests.unit_tests.research.test_parent_measurement import parent_fixture
        store,owner,fixture,binding=await parent_fixture(tmp_path)
        prepare=owner.prepare_admitted_measurement;execute=owner.execute_admitted_measurement
        kinds=('parent-reservation-claim','admitted-parent-grant','model-call-start')
    pin=fixture['put'](binding);owner.library.rsi_security_guard=None
    before=[row['ref'] for row in store.iter_records(kinds=kinds)]
    try:
        with pytest.raises(ResearchError,match='qualification'):prepare(pin)
        assert before==[row['ref'] for row in store.iter_records(kinds=kinds)]
        # Controlled constructor capability permits only fixture construction;
        # removal before execute must still block, without a reservation charge.
        owner.library.rsi_security_guard=ControlledQualification();grant=prepare(pin)
        owner.library.rsi_security_guard=None
        with pytest.raises(ResearchError,match='qualification'):await execute(grant)
        assert not list(store.iter_records(kinds=('isolated-reservation-claim','parent-reservation-claim','model-call-start')))
    finally:store.close()


@pytest.mark.asyncio
async def test_actual_worker_rpc_refuses_unqualified_helper_before_durable_claim_or_spawn(tmp_path):
    from jiuwenswarm.research.private_rpc import PrivateRPCServer,PrivateRPCClient
    from jiuwenswarm.research.router_client import PlatformIntegrityError
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.worker import WorkerBroker,PROTOCOL
    assert hasattr(os,'getuid'),'BLOCKED: Linux peer identity required'
    records=RecordStore(tmp_path/'records')
    class Public:
        def get(self,pin):return records.get(pin)
        def read(self,pin):return records.read(pin)
    session=records.put({'scope':'negative IPC fixture; not qualification'})
    candidate=records.put_bytes(b'def rank_opportunities(scores): return {}')
    profile=records.put({'schema':'ai4r-rsi-worker-profile:1','target_kind':'ranking-v1',
        'session_ref':session,'target_ref':session,'parent_ref':candidate,'contract_ref':session,
        'environment_ref':session,'hardware_ref':session,'memory_mb':128,'pids_max':16,'timeout_s':1})
    reservation=records.put({'session_ref':session,'candidate_ref':candidate,'phase':'development','operation':'mandatory:control'})
    inputs=records.put({'scores':[]});root=tmp_path/'worker'
    broker=WorkerBroker(root=root,cgroup_root=tmp_path/'not-a-qualified-cgroup',profiles=[profile],
        public_reader=Public(),input_reader=Public(),capture_store=records,hidden=False)
    socket=tmp_path/'ipc'/'worker.sock'
    server=PrivateRPCServer(socket,protocol=PROTOCOL,session_id='negative-qualification-control',capability='control-only',
        handlers={'run_helper':broker.run},allowed_uids={os.getuid()})
    await server.start()
    try:
        client=PrivateRPCClient(socket,protocol=PROTOCOL,session_id='negative-qualification-control',capability='control-only',peer_uid=os.getuid())
        with pytest.raises(PlatformIntegrityError):
            await client.call('run_helper',{'profile_ref':profile,'session_ref':session,'candidate_ref':candidate,
                'input_ref':inputs,'reservation_ref':reservation,'phase':'development','repeat_index':0})
        assert not list(root.glob('claim-*')) and not broker.claims and not broker.tasks and not broker.executor.active
    finally:
        await server.close();records.close()
        assert not socket.exists()
