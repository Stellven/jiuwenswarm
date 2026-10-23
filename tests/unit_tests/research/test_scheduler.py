"""Protected scheduler stop controls; component fixtures are not live acceptance."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.runner import ProducedArtifact
from jiuwenswarm.research.scheduler import Scheduler
from tests.unit_tests.research.test_admitted_measurement import adapter_fixture


@pytest.mark.asyncio
@pytest.mark.parametrize('reason',['integrity_fault','security_fault','AUDIT_UNAVAILABLE'])
async def test_partial_output_retains_source_null_reason_and_protected_stop_receipt(tmp_path,reason):
    store,adapter,contract_ref,plan_ref,_=await adapter_fixture(tmp_path)
    runner=adapter.runner;contract=store.read_record(contract_ref);binding=contract['bindings'][0]
    parent=store.read_record(contract['node_contract_ref']);expected=adapter.resources.exact_binding_refs
    runner.configure_run(contract['run_id'],**{k:expected[k] for k in ('model_selection_profile_ref','deployment_ref','configuration_ref')},
        router={'enabled':False,'deadline_s':30,'profile_ref':None},run_limits=parent['node_limits'])
    first=json.loads(Path('tests/fixtures/research/pipeline/source-valid/screening_result.json').read_bytes())
    first.pop('ext',None)
    class Partial:
        async def execute(self,*_):
            return {'screening_result':ProducedArtifact(first),'opportunity_card':ProducedArtifact({'controlled_second':True})}
    identity=store.read_record(binding['declaration_ref'])['identity']
    key=(identity['name'],identity['version_label'],binding['declaration_ref']['sha256'])
    runner.registry._handlers[key]=(Partial(),tuple(binding['implementation_refs']))
    original=store.put_blob
    def capture(raw,**kwargs):
        if raw==b'{"controlled_second":true}':raise ResearchError(reason,'Explicit controlled protected failure after first capture')
        return original(raw,**kwargs)
    store.put_blob=capture
    template=store.read_record(contract['template_ref']);bundle=store.read_record(template['check_bundle_ref'])
    result=await runner.run(contract_ref,plan_ref,bundle_id=bundle['bundle_id'])
    observation=store.read_record(result.observation_ref)
    assert result.output_refs and observation['failure_reason_code'] is None and not result.accepted
    assert next(value for value in runner._executions.values() if value['observation_ref']==result.observation_ref)['failure']==reason
    stop_ref=getattr(result,'protected_stop_ref',None)
    assert stop_ref is not None,'Partial capture must retain the protected stop outside the source nullable field'
    stopped=store.read_record(stop_ref)
    assert stopped['reason_code']==reason and stopped['worker_observation_ref']==result.observation_ref
    assert stopped['contract_ref']==contract_ref and stopped['failure_observation_ref']==result.observation_ref
    assert not store.accepted_outputs(contract['run_id'],contract['node_id'])


@pytest.mark.asyncio
@pytest.mark.parametrize('reason',['integrity_fault','security_fault','AUDIT_UNAVAILABLE','run_budget_exhausted','foreign_run','foreign_observation','unknown_reason',None])
async def test_scheduler_stops_independent_dispatch_on_exact_protected_receipt(monkeypatch,reason):
    # In-memory finite trusted-component seams isolate the actual Scheduler
    # causal decision; the preceding test exercises the real Runner capture.
    def ref(name):return {'id':name,'sha256':'a'*64}
    cc={'cc_name':'controlled.worker','cc_version':'unit','declaration_sha256':'b'*64}
    nodes=[{'node_id':name,'predecessors':[],'cc':cc,'inputs':[],'outputs':[],
        'objective':'Controlled scheduler stop','requirement_ids':['unit'],'deliverable_ids':[],
        'limits':{'time_s':30,'model_calls':0,'memory_mb':64},'check_pins':{}} for name in ('a','independent')]
    plan={'frozen':True,'nodes':nodes,'topological_order':['a','independent'],'library_snapshot_ref':ref('snapshot'),
        'limits':{'time_s':60},'policy_ref':ref('policy'),'configuration_ref':ref('configuration'),'source_ref':ref('source')}
    records={'plan':plan,'snapshot':{'entries':[dict(cc,input_ports=[],output_ports=[])]}}
    dispatched=[];states=[]
    class Store:
        def read_record(self,value,**_):return records[value['id']]
        def record_kind(self,_):return 'protected-invocation-stop'
        def cancellation_requested(self,*_):return False
        def set_node_state(self,*_,**__):pass
        def set_run_state(self,run,state,**_):states.append(state)
        def authorize_dispatch(self,*_,**__):pass
        def predecessor_snapshot(self,*_,**__):return []
    class Factory:
        def prepare_parent(self,run,node,*_,**__):
            records['parent']={'subnodes':[]};return ref('parent')
        def bind_subnode(self,*_,**__):return ref('work'),ref('checks'),'unit'
    class Runner:
        def prepare_node_check_plan(self,*_,**__):return ref('node-checks')
        def dispatch_timing(self,*_,**__):
            import time
            return {'started_at':'2026-10-20T00:00:00Z','started_monotonic_s':time.monotonic()}
        async def run(self,*_,**__):
            node=nodes[len(dispatched)]['node_id'];dispatched.append(node)
            records['observation']={'contract_ref':ref('work'),'failure_reason_code':None,'run_id':'run','node_id':node,
                'attempt_id':node+'-a1','node_contract_ref':ref('parent')}
            records['stop']={'schema':'ai4r-protected-invocation-stop:1','run_id':'run','node_id':node,
                'contract_ref':ref('work'),'worker_observation_ref':ref('observation'),'failure_observation_ref':ref('observation'),'reason_code':reason}
            if reason in {'foreign_run','foreign_observation','unknown_reason'}:records['stop']['reason_code']='integrity_fault'
            if reason=='foreign_run':records['stop']['run_id']='another-run'
            if reason=='foreign_observation':records['stop']['worker_observation_ref']=ref('foreign')
            if reason=='unknown_reason':records['stop']['reason_code']='output_invalid'
            return SimpleNamespace(accepted=False,output_refs={},observation_ref=ref('observation'),
                protected_stop_ref=ref('stop') if reason else None)
        async def finalize_node(self,*_,**__):records['decision']={'action':'stop'};return ref('decision')
        def capture_dispatch(self,*_,**__):pass
    async def serial(order,dispatch,**_):
        for node in order:await dispatch(node)
    monkeypatch.setattr('jiuwenswarm.research.scheduler.run_native_workflow',serial)
    scheduler=Scheduler(Store(),Runner(),Factory(),SimpleNamespace(validate_acceptance=lambda _:None),library=None)
    if reason:
        with pytest.raises(ResearchError,match='protected_stop'):
            await scheduler.execute_plan('run',ref('plan'),{'authority_ceiling':{'resource_reads':[]}})
        assert dispatched==['a'] and states==['halted']
    else:
        result=await scheduler.execute_plan('run',ref('plan'),{'authority_ceiling':{'resource_reads':[]}})
        assert dispatched==['a','independent'] and result['status']=='partial'


@pytest.mark.parametrize('exhausted',[None,'calls','time'])
def test_node_budget_failure_only_halts_globally_when_actual_run_ceiling_is_exhausted(tmp_path,exhausted):
    import time
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research.runner import CapsuleRunner,Registry
    from jiuwenswarm.research.state import SQLiteRunStore
    store=SQLiteRunStore(tmp_path);store.create_run('run',account_id='operator',workspace_id='unit',submission={})
    runner=CapsuleRunner(store,Registry(),CheckRegistry(),model=None);opaque=store.put_blob(b'explicit controlled budget context')
    runner.configure_run('run',model_selection_profile_ref=opaque,deployment_ref=opaque,configuration_ref=opaque,
        router={'enabled':False},run_limits={'time_s':30,'model_calls':1 if exhausted=='calls' else 2,'memory_mb':64})
    store.claim_model_call({'run_id':'run','node_id':'node','attempt_id':'node-a1','invocation_id':'unit','call_ordinal':1},invocation_limit=1,node_limit=1,run_limit=2)
    if exhausted=='time':runner._run_started['run']=time.monotonic()-31
    contract={'run_id':'run','node_id':'node','attempt_id':'node-a1','node_contract_ref':opaque}
    receipt=runner._capture_protected_stop(opaque,contract,opaque,'wall_clock_exhausted')
    assert (receipt is not None) is (exhausted is not None)
    if receipt:assert store.read_record(receipt)['reason_code']=='run_budget_exhausted'


@pytest.mark.asyncio
@pytest.mark.parametrize('disposition', ['allow', 'refuse', 'cancel'])
async def test_scheduler_does_not_publish_start_before_awaited_owner_boundary(tmp_path, monkeypatch, disposition):
    """Actual source Factory/Scheduler/Runner; held boundary is a negative fault.

    The fixture is a real finite nonscientific controlled request. This proves
    chronology and refusal handling, never native/GPU/service qualification.
    """
    import asyncio
    from tests.unit_tests.research.test_finite_e1 import finite_execution_fixture
    store, owner, protected, _, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid')
    runner = scheduler.runner
    entered, release = asyncio.Event(), asyncio.Event()
    original = runner._await_start
    contexts = []

    async def held(context, **kwargs):
        contexts.append(context)
        entered.set()
        await release.wait()
        if disposition == 'refuse':
            raise ResearchError('SCIENCE_RUNTIME_BINDINGS_UNAVAILABLE', 'Controlled refusal before consumed start')
        return await original(context, **kwargs)

    monkeypatch.setattr(runner, '_await_start', held)
    task = asyncio.create_task(owner.execute('run:finite-visible', protected, scheduler=scheduler))
    observed = None
    assertion_failure = None
    try:
        await asyncio.wait_for(entered.wait(), 20)
        assert not list(store.iter_records(kinds=('dispatch-start',))), \
            'Scheduler published dispatch-start before the actual awaited start boundary'
        with store._lock:
            states = [row[0] for row in store.connection.execute('SELECT state FROM nodes')]
        assert states and set(states) == {'pending'}, 'Inert preparation must not publish Running'
        assert not list(store.iter_records(kinds=('invocation-observation', 'model-call-claim',
            'model-call-start', 'gate-decision', 'acceptance-commit')))
        assert prompts == [] and len(contexts) == 1
        if disposition == 'cancel':
            store.request_cancellation('run:finite-visible', 'owner', 'cancel:held-start')
    except BaseException as error:
        assertion_failure = error
    finally:
        release.set()
        if not entered.is_set():
            task.cancel()
        observed = (await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 30))[0]
    try:
        if assertion_failure is not None:
            raise assertion_failure
        if disposition == 'allow':
            assert not isinstance(observed, BaseException), repr(observed)
            assert observed['status'] == 'completed' and len(prompts) == 3
            assert len(list(store.iter_records(kinds=('dispatch-start',)))) == 1
        else:
            assert prompts == []
            assert not list(store.iter_records(kinds=('dispatch-start', 'invocation-observation',
                'model-call-claim', 'gate-decision', 'acceptance-commit')))
            dispatches = list(store.iter_records(kinds=('dispatch-record',)))
            assert len(dispatches) == 1, 'Genuine complete source closure must retain the failed zero-worker dispatch'
            dispatch = dispatches[0]['record']
            assert dispatch['outcome'] in {'failed', 'budget_exhausted', 'interrupted'}
            assert dispatch['gate_decision_ref'] is None and dispatch['output_gate_decision_refs'] == []
            assert dispatch['output_refs'] == [] and dispatch['elapsed_s'] is not None
            assert store.record_kind(dispatch['check_plan_ref']) == 'bound-check-plan'
            plan = store.read_record(dispatch['check_plan_ref'])
            assert plan['subnode_id'] is None and plan['node_contract_ref'] == dispatch['node_contract_ref']
            assert len(list(store.iter_records(kinds=('invocation-preparation',)))) == 1
    finally:
        store.close()
