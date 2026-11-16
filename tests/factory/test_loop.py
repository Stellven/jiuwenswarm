"""Offline durability tests use a fake benchmark adapter, never Docker/GPU."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from jiuwenswarm.factory.loop import FactoryLoop, dispatch
from jiuwenswarm.factory.store import PersistenceFailed, ScopeDenied, StaleRevision, Store


@pytest.fixture
def setup_loop(tmp_path):
    from jiuwenswarm.factory.benchmark import EXECUTION_FILES
    args=['--pack','/pack','--max-context','8192','--eos','1','--vision','off',
        '--dspark','none','--prefill-chunk','256','--cpu-threads','8','--vram-experts','1.0',
        '--reserve-mib','16384','--ssd-cache','0','--mmap-experts','on','--experts','6',
        '--dspark-conf','0.65','--no-expert-cache']
    a=dict(args=args,environment={'STRATA_DS4_REUSE':'0'}); b=copy.deepcopy(a)
    b['args'][b['args'].index('--dspark')+1]='on'
    contract=dict(adapter='strata-benchmark-v1',version=1,stage='pilot',target='spark-gb10',
        tolerance='arc-exact-answer-regression-v1',image={'id':'sha256:'+'a'*64},
        arms={'A':a,'B':b},order=['A','B'],workload={'pack':'/pack'},
        limits=dict(cpus=8,memory_bytes=104*2**30,guard_gib=8,extra_swap_bytes=0,quality_timeout_s=900,speed_timeout_s=300),
        gates=dict(minimum_accuracy=.5,minimum_speedup=1.05,confidence=.95,bootstrap_resamples=20000,seed=42,correctness='no_per_question_regression'),
        campaign_timeout_s=60,dataset_sha256='a'*64,execution_sha256={f:'a'*64 for f in EXECUTION_FILES})
    template=tmp_path/'template.json'; template.write_text(json.dumps(contract))
    policy=dict(max_cycles=2,max_experiments=2,wall_clock_s=100,
        templates=[dict(id='draft-pilot',path=str(template),sha256=hashlib.sha256(template.read_bytes()).hexdigest(),allowed_hypothesis_ids=['measure_io_readiness','measure_placement'])])
    store=Store(tmp_path/'store')
    store.create_task(dict(task_id='parent',objective='Measured engine improvement',contract_id='original-unchanged',
        constraints={'factory_loop':policy},allowed_effects=['process.exec','gpu.use']))
    store.append_observation('parent',dict(obs_id='seed',kind='report',values={'status':'success'}))
    yield store, template
    store.close()


class FakeBenchmark:
    """Only durable identity/lifecycle are fake; factory storage is real SQLite."""
    def __init__(self, store):
        self.store=store; self.crash=False; self.calls=0; self.state='succeeded'

    def submit(self, task_id, contract_id, idem_key):
        self.calls+=1
        rows=self.store._db.execute('SELECT attempt_id FROM attempts WHERE task_id=? AND idem_key=?', (task_id,idem_key)).fetchall()
        if rows:
            return self.store.read(task_id,rows[0]['attempt_id'])
        attempt=self.store.create_attempt(task_id,dict(kind='lab',idem_key=idem_key,fingerprint='fake',request={'contract_id':contract_id}))
        if self.crash:
            self.crash=False
            raise RuntimeError('Injected lost queue acknowledgement')
        return attempt

    def result(self, task_id, attempt_id):
        self.store.read(task_id,attempt_id)
        return dict(attempt_id=attempt_id,state=self.state,
            analysis=dict(status='success' if self.state=='succeeded' else 'failed',verdict='pilotPass' if self.state=='succeeded' else 'inconclusive'))


def choose(loop, cycle='one', evidence='seed', rev=0):
    return loop.select(cycle,[evidence],'measure_io_readiness','draft-pilot',rev)


def test_two_actual_host_cycles_execute_collect_and_budget(setup_loop):
    store,_=setup_loop; adapter=FakeBenchmark(store)
    loop=FactoryLoop(store,'parent',benchmark=adapter,clock=lambda:10)
    before=store.get_task('parent')['contract_id']
    one=choose(loop); assert one['state']=='selected'
    sent=loop.execute('one'); assert sent['state']=='submitted'
    result=loop.collect('one'); assert result['state']=='collected'
    assert result['followup']['requires_operator_admission'] is True
    choose(loop,'two',result['evidence_id'],1)
    loop.execute('two');loop.collect('two')
    with pytest.raises(ValueError,match='budget exhausted'):
        choose(loop,'three','loop-result:2',2)
    assert len(loop.status()['cycles'])==2
    assert adapter.calls==2
    assert store.get_task('parent')['contract_id']==before
    child=store.get_task('parent-loop-1')
    assert child['contract_id']!=before
    assert child['allowed_effects']==store.get_task('parent')['allowed_effects']
    assert hashlib.sha256(Path(child['contract_id']).read_bytes()).hexdigest()==child['constraints']['benchmark_contract_sha256']


def test_restart_after_lost_queue_ack_recovers_one_attempt_even_after_deadline(setup_loop):
    store,_=setup_loop; adapter=FakeBenchmark(store); adapter.crash=True
    loop=FactoryLoop(store,'parent',benchmark=adapter,clock=lambda:10)
    choose(loop)
    with pytest.raises(RuntimeError,match='lost queue'):
        loop.execute('one')
    assert loop.status()['cycles'][0]['state']=='dispatching'
    resumed=FactoryLoop(store,'parent',benchmark=adapter,clock=lambda:1000)
    recovered=resumed.execute('one')
    assert recovered['state']=='submitted'
    assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0]==1
    assert resumed.collect('one')['state']=='collected'
    with pytest.raises(ValueError,match='wall clock'):
        choose(resumed,'two','loop-result:1',1)


def test_selection_replay_and_stale_revision_and_template_scope(setup_loop):
    store,template=setup_loop; loop=FactoryLoop(store,'parent',clock=lambda:10)
    first=choose(loop)
    assert choose(loop)==first
    with pytest.raises(ValueError,match='replay conflicts'):
        loop.select('one',['seed'],'measure_placement','draft-pilot',0)
    with pytest.raises(ScopeDenied):
        loop.select('two',['seed'],'measure_placement','unapproved',1)
    template.write_text('{}')
    with pytest.raises(ValueError,match='identity changed'):
        choose(loop,'two',rev=1)
    assert len(loop.status()['cycles'])==1


def test_crash_before_selection_commit_spends_no_budget(setup_loop):
    store,_=setup_loop; loop=FactoryLoop(store,'parent',clock=lambda:10)
    store.fault=lambda stage: (_ for _ in ()).throw(RuntimeError('crash'))
    with pytest.raises(PersistenceFailed):choose(loop)
    store.fault=None
    assert loop.status()['remaining_cycles']==2
    assert store.get_task('parent')['current_decision_rev']==0
    assert choose(loop)['number']==1


def test_stop_blocks_fresh_effects_and_failed_results_are_retained(setup_loop):
    store,_=setup_loop; adapter=FakeBenchmark(store);adapter.state='failed'
    loop=FactoryLoop(store,'parent',benchmark=adapter,clock=lambda:10)
    choose(loop);loop.execute('one');loop.stop('operator stop')
    result=loop.collect('one')
    assert store.read('parent',result['evidence_id'])['values']['status']=='failed'
    assert loop.collect('one')==result
    with pytest.raises(ValueError,match='stopped'):
        choose(loop,'two',result['evidence_id'],1)


def test_strict_input_scope_and_cc_seals(setup_loop,tmp_path):
    store,_=setup_loop
    with pytest.raises(ValueError):dispatch(store,'parent','execute',{'cycle_id':'one','contract':{}})
    store.create_task(dict(task_id='foreign',objective='private'))
    with pytest.raises(ScopeDenied):FactoryLoop(store.scoped('parent'),'foreign')
    from jiuwenswarm.ccv2.ccv2 import Host
    host=Host(tmp_path/'ccstore',session_grants=['process.exec'])
    release=host.prepare(Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/engine_factory_loop')
    assert host.material(release,'methodology')


def test_template_hypothesis_binding_cannot_be_substituted(setup_loop):
    store,_=setup_loop
    loop=FactoryLoop(store,'parent',clock=lambda:10)
    with pytest.raises(ScopeDenied,match='Hypothesis is not admitted'):
        loop.select('wrong',['seed'],'measure_cpu_scheduling','draft-pilot',0)
    assert loop.status()['remaining_experiments']==2


def test_child_attempts_belong_to_parent_controller_and_supervisor_only_via_ledger(setup_loop):
    store,_=setup_loop; adapter=FakeBenchmark(store)
    loop=FactoryLoop(store,'parent',benchmark=adapter,clock=lambda:10)
    choose(loop);sent=loop.execute('one')
    store.create_task(dict(task_id='forged-child',objective='unrelated',constraints={'factory_loop_parent':'parent'}))
    store.create_attempt('forged-child',dict(kind='lab',idem_key='fake',fingerprint='fake',request={}))
    from jiuwenswarm.factory.loop import owned_attempts
    assert [a['attempt_id'] for a in owned_attempts(store,'parent')]==[sent['attempt_id']]
    from jiuwenswarm.factory.controller import Controller
    controller=Controller(store=store,jobs=object())
    assert [a['attempt_id'] for a in controller._snapshot('parent')['attempts']]==[sent['attempt_id']]
    from jiuwenswarm.factory.mission_supervisor import Supervisor
    supervisor=object.__new__(Supervisor);supervisor.home=store.home;supervisor.task='parent'
    assert [a['attempt_id'] for a in supervisor.attempts()]==[sent['attempt_id']]


def test_operator_driver_runs_pilot_then_main_honestly_with_fake_adapter(setup_loop,monkeypatch):
    import importlib.util
    import sys
    from types import SimpleNamespace
    store,_=setup_loop;adapter=FakeBenchmark(store)
    original_result=adapter.result
    def result(task_id,attempt_id):
        output=original_result(task_id,attempt_id)
        output['analysis']['verdict']='pilot_ok'
        return output
    adapter.result=result
    path=Path(__file__).resolve().parents[2]/'deploy/spark/run-factory-campaign.py'
    spec=importlib.util.spec_from_file_location('factory_campaign_driver',path)
    driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
    monkeypatch.setattr(driver,'FactoryLoop',lambda store,task:FactoryLoop(store,task,benchmark=adapter))
    monkeypatch.setattr(driver.subprocess,'run',lambda *a,**kw:SimpleNamespace(stdout=''))
    monkeypatch.setattr(sys,'argv',[str(path),'--home',str(store.home),'--task','parent',
        '--evidence-id','seed','--hypothesis-id','measure_io_readiness',
        '--pilot-template','draft-pilot','--main-template','draft-pilot','--operator-host-quiet'])
    assert driver.main()==0
    cycles=FactoryLoop(store,'parent').status()['cycles']
    assert [c['state'] for c in cycles]==['collected','collected']
    from jiuwenswarm.factory.mission_supervisor import mission_root
    receipt=json.loads((mission_root(store.home,'parent')/'quiet'/(cycles[0]['attempt_id']+'.json')).read_text())
    assert receipt['mode']=='operator_host' and receipt['llm_agent'] is False
    assert receipt['proof']['controller_lock_held'] is True


def test_scoped_workbench_routes_full_loop_and_supervisor_import(setup_loop, monkeypatch):
    """Adapter-interface test; fake scientific validator never represents live evidence."""
    import sys
    from types import ModuleType
    from jiuwenswarm.factory.mission_supervisor import Supervisor
    store,template=setup_loop
    contract=json.loads(template.read_text());contract['adapter']='strata-prefill-scoped-v1'
    scoped_path=template.parent/'scoped-interface-test.json';scoped_path.write_text(json.dumps(contract))
    policy=copy.deepcopy(store.get_task('parent')['constraints']['factory_loop'])
    policy['templates'][0].update(path=str(scoped_path),sha256=hashlib.sha256(scoped_path.read_bytes()).hexdigest())
    store.create_task(dict(task_id='scoped-parent',objective='Adapter routing only',constraints={'factory_loop':policy}))
    store.append_observation('scoped-parent',dict(obs_id='seed',values={'status':'success'}))
    adapter=FakeBenchmark(store);validated=[]
    module=ModuleType('jiuwenswarm.factory.prefill_workbench')
    module.Workbench=lambda host:adapter
    module.validate_contract=lambda c:(validated.append(c['adapter']) or c)
    monkeypatch.setitem(sys.modules,module.__name__,module)
    loop=FactoryLoop(store,'scoped-parent',clock=lambda:10)
    choose(loop);sent=loop.execute('one');collected=loop.collect('one')
    assert validated==['strata-prefill-scoped-v1']
    assert collected['state']=='collected' and adapter.calls==1
    imported=[];adapter.result=lambda task,attempt:imported.append((task,attempt))
    Supervisor._import_result(object.__new__(Supervisor),store,object(),dict(task_id='scoped-parent-loop-1',
        attempt_id=sent['attempt_id'],request={'adapter':'strata-prefill-scoped-v1'},result_refs=[]))
    assert imported==[('scoped-parent-loop-1',sent['attempt_id'])]


def test_optional_qualification_gate_reassesses_instead_of_trusting_saved_verdict(setup_loop, monkeypatch):
    from jiuwenswarm.factory import cc_qualification
    store,_=setup_loop
    task=store.get_task('parent')
    task['constraints']['cc_qualification']={'policies':[{'id':'configuration'}]}
    with store._transaction():
        store._db.execute('UPDATE tasks SET constraints=? WHERE task_id=?',(json.dumps(task['constraints']),'parent'))
    loop=FactoryLoop(store,'parent',clock=lambda:10)
    with pytest.raises(ScopeDenied,match='qualification'):choose(loop)
    store.append_observation('parent',dict(obs_id='claimed-qualified',kind='cc_admission_assessment',
        values=dict(policy_id='configuration',verification_ids=['unit-proof'],verdict='eligible')))
    calls=[]
    def stale(*args):
        calls.append(args[2:]);raise ValueError('Current source/checker identity differs')
    monkeypatch.setattr(cc_qualification,'assess_admission',stale)
    with pytest.raises(ScopeDenied,match='stale'):choose(loop)
    assert calls==[('configuration',['unit-proof'])]
    assert loop.status()['remaining_cycles']==2
    store.append_observation('parent',dict(obs_id='rechecked-qualification',kind='cc_admission_assessment',values={'proof':'independently checked'}))
    def eligible(*args):
        calls.append(args[2:]);return dict(eligibility={'verdict':'eligible'},observation_id='rechecked-qualification')
    monkeypatch.setattr(cc_qualification,'assess_admission',eligible)
    cycle=choose(loop)
    assert cycle['qualification_ids']==['rechecked-qualification']
    decision=store.read('parent','parent:decision:1')
    assert 'rechecked-qualification' in decision['evidence_ids']


def linked_loop(tmp_path, *, gpu_seconds=180, require=True):
    """Real task/graph/loop storage; fake external benchmark only."""
    from jiuwenswarm.factory.branch_workbench import dispatch as branch
    from jiuwenswarm.factory.benchmark import EXECUTION_FILES
    # Reuse the already validated fixture contract without a second schema copy.
    tmp_path.mkdir(parents=True, exist_ok=True)
    generator = setup_loop.__wrapped__(tmp_path)
    store, template = next(generator)
    task = store.get_task('parent')
    policy = copy.deepcopy(task['constraints']['factory_loop'])
    policy['require_branch_binding'] = require
    store.create_task(dict(task_id='linked', objective='Connected investigation',
        constraints={'factory_loop': policy, 'branch_workbench': {
            'max_branches': 4, 'cpu_seconds': 30, 'gpu_seconds': 600}},
        allowed_effects=['process.exec','gpu.use']))
    store.append_observation('linked', dict(obs_id='seed',kind='report',values={'status':'success'}))
    store.advance_decision('linked',0,{'hypothesis':'Compare admitted alternatives'})
    branch(store,'linked','create',dict(node_id='candidate',hypothesis='measure_io_readiness',
        allocation={'cpu_seconds':10,'gpu_seconds':gpu_seconds},expected_graph_rev=0,
        decision_rev=1,idem_key='create'))
    return generator, store, FakeBenchmark(store), policy


def linked_select(loop, **overrides):
    kwargs=dict(cycle_id='one',evidence_ids=['seed'],hypothesis_id='measure_io_readiness',
        template_id='draft-pilot',expected_rev=1,branch_id='candidate',expected_graph_rev=1)
    kwargs.update(overrides)
    return loop.select(**kwargs)


def test_branch_cycle_collect_unlocks_continuation_and_preserves_unknown_metrics(tmp_path):
    from jiuwenswarm.factory import branch_workbench as bw
    gen,store,adapter,_=linked_loop(tmp_path)
    try:
        loop=FactoryLoop(store,'linked',benchmark=adapter,clock=lambda:10)
        chosen=linked_select(loop)
        assert chosen['branch_binding']['worker_bound_s']==180
        assert linked_select(loop)==chosen
        with pytest.raises(ScopeDenied,match='explicit branch'):
            loop.select('missing',['seed'],'measure_io_readiness','draft-pilot',2)
        sent=loop.execute('one');result=loop.collect('one')
        assert loop.collect('one')==result
        status=bw.status(store,'linked');row=status['branches'][0]
        assert row['state']=='done' and row['measurement'] is None
        assert row['experiment_cycles'][0]['attempt_id']==sent['attempt_id']
        assert row['experiment_cycles'][0]['evidence_id']==result['evidence_id']
        assert result['evidence_id'] in row['evidence_ids']
        assert bw.compare(store,'linked')['unknown']==['candidate']
        next_state=bw.dispatch(store,'linked','refine',dict(node_id='next',parent_id='candidate',
            hypothesis='measure_placement',allocation={'cpu_seconds':10,'gpu_seconds':180},
            expected_graph_rev=status['graph_rev'],decision_rev=2,idem_key='next'))['analysis']
        assert next_state['ready']==['next']
        assert adapter.calls==1
    finally:gen.close()


@pytest.mark.parametrize('change,exc', [
    ({'expected_graph_rev':0},StaleRevision),
    ({'branch_id':'foreign'},ScopeDenied),
    ({'hypothesis_id':'measure_placement'},ScopeDenied),
    ({'expected_graph_rev':None},ValueError),
])
def test_branch_selection_rejects_mismatch_atomically(tmp_path,change,exc):
    gen,store,adapter,_=linked_loop(tmp_path)
    try:
        loop=FactoryLoop(store,'linked',benchmark=adapter,clock=lambda:10)
        with pytest.raises(exc):linked_select(loop,**change)
        assert loop.status()['remaining_cycles']==2
        assert store.get_task('linked')['current_decision_rev']==1
        assert adapter.calls==0
    finally:gen.close()


def test_branch_reservation_covers_worker_bound(tmp_path):
    gen,store,adapter,_=linked_loop(tmp_path,gpu_seconds=179)
    try:
        loop=FactoryLoop(store,'linked',benchmark=adapter,clock=lambda:10)
        with pytest.raises(ScopeDenied,match='reservation'):linked_select(loop)
        assert not loop.status()['cycles']
    finally:gen.close()


@pytest.mark.parametrize('lost_ack',[False,True])
def test_pruned_branch_blocks_new_dispatch_but_recovers_existing_attempt(tmp_path,lost_ack):
    from jiuwenswarm.factory import branch_workbench as bw
    gen,store,adapter,_=linked_loop(tmp_path)
    try:
        loop=FactoryLoop(store,'linked',benchmark=adapter,clock=lambda:10)
        linked_select(loop)
        if lost_ack:
            adapter.crash=True
            with pytest.raises(RuntimeError):loop.execute('one')
        state=bw.status(store,'linked')
        bw.dispatch(store,'linked','prune',dict(node_id='candidate',reason='Stop this lead',
            expected_graph_rev=state['graph_rev'],decision_rev=2,idem_key='prune'))
        recovered=FactoryLoop(store,'linked',benchmark=adapter,clock=lambda:1000 if lost_ack else 10)
        if lost_ack:
            recovered.execute('one');result=recovered.collect('one')
            assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0]==1
            row=bw.status(store,'linked')['branches'][0]
            assert row['state']=='cancelled'
            assert row['experiment_cycles'][0]['evidence_id']==result['evidence_id']
        else:
            with pytest.raises(ValueError,match='cancelled'):recovered.execute('one')
            assert adapter.calls==0
    finally:gen.close()


def test_abandon_spends_reservation_and_cannot_hide_lost_ack(tmp_path):
    gen,store,adapter,_=linked_loop(tmp_path)
    try:
        loop=FactoryLoop(store,'linked',benchmark=adapter,clock=lambda:10)
        linked_select(loop)
        result=loop.abandon('one','Different diagnostic needed')
        assert result['result']['analysis']['measured'] is False
        assert result['state']=='collected'
        assert loop.status()['remaining_cycles']==1
        assert loop.abandon('one','Different diagnostic needed')==result
        with pytest.raises(ValueError,match='replay'):loop.abandon('one','Changed')
        assert adapter.calls==0
    finally:gen.close()
    gen,store,adapter,_=linked_loop(tmp_path/'lost')
    try:
        loop=FactoryLoop(store,'linked',benchmark=adapter,clock=lambda:10)
        linked_select(loop);adapter.crash=True
        with pytest.raises(RuntimeError):loop.execute('one')
        with pytest.raises(ScopeDenied,match='existing attempt'):loop.abandon('one','Hide lost acknowledgement')
        assert loop.execute('one')['state']=='submitted'
    finally:gen.close()


def test_actual_native_host_select_links_branch_and_abandon(tmp_path,monkeypatch):
    import sys
    from jiuwenswarm.ccv2.ccv2 import Host
    gen,store,adapter,_=linked_loop(tmp_path)
    try:
        monkeypatch.setenv('FACTORY_HOME',str(store.home))
        monkeypatch.setenv('FACTORY_TASK_ID','linked')
        monkeypatch.setenv('FACTORY_PYTHON',sys.executable)
        monkeypatch.setenv('PYTHONPATH',str(Path(__file__).resolve().parents[2]))
        host=Host(tmp_path/'native-calls',python=sys.executable)
        release=host.prepare(Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/engine_factory_loop')
        selected=host.call(release,'select',dict(cycle_id='native',evidence_ids=['seed'],
            hypothesis_id='measure_io_readiness',template_id='draft-pilot',expected_rev=1,
            branch_id='candidate',expected_graph_rev=1),grants=['process.exec'])
        assert selected['state']=='succeeded',selected
        assert selected['outputs']['result']['branch_binding']['node_id']=='candidate'
        closed=host.call(release,'abandon',dict(cycle_id='native',reason='Native transport qualified'),grants=['process.exec'])
        assert closed['state']=='succeeded',closed
        assert closed['outputs']['result']['result']['analysis']['measured'] is False
        assert adapter.calls==0
    finally:gen.close()


@pytest.mark.parametrize('state', ['queued', 'unknown', 'cancel_requested'])
def test_parent_terminal_waits_for_child_and_collection(setup_loop, state):
    from jiuwenswarm.factory.controller import Controller
    store, _ = setup_loop
    adapter = FakeBenchmark(store); adapter.state = 'failed'
    loop = FactoryLoop(store, 'parent', benchmark=adapter, clock=lambda: 10)
    choose(loop); sent = loop.execute('one')
    child, attempt = sent['child_task_id'], sent['attempt_id']
    if state != 'queued':
        store.transition_attempt(child, attempt, state)
    store.advance_decision('parent', 1, dict(action={'type': 'reject'}, evidence_ids=['seed']))
    controller = Controller(store=store, jobs=object())
    assert controller._terminal_ready('parent') is False
    store.transition_attempt(child, attempt, 'failed')
    assert controller._terminal_ready('parent') is False  # terminal execution is not collection
    loop.stop('parent ending; retain child failure')
    result = loop.collect('one')
    assert result['result']['analysis']['verdict'] == 'inconclusive'
    assert store.read('parent', result['evidence_id'])['host_run'] == dict(child_task_id=child, attempt_id=attempt)
    store.advance_decision('parent', 2, dict(action={'type': 'reject'}, evidence_ids=[result['evidence_id']]))
    assert controller._terminal_ready('parent') is True
