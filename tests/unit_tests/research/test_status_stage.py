"""Original chronology display mechanics; controlled eligibility/replies, no science claims."""
import asyncio
import copy
import shutil
import sqlite3
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.control import ResearchService
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from tests.unit_tests.research.test_finite_e1 import finite_execution_fixture


@asynccontextmanager
async def stage_fixture(tmp_path, *, fault='valid', segment=False):
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, fault, segment=segment)
    service = ResearchService(store, registry=scheduler.runner.registry, model=scheduler.runner.model,
        profiles=owner._component_profiles, binder=scheduler.binder, scheduler=scheduler, finite_e1=owner)
    service.configure_workspace('owner', 'work', **protected)
    principal = Principal('owner', frozenset({'work'}), frozenset({'submit', 'status', 'reconcile'}))
    f = SimpleNamespace(store=store, owner=owner, protected=protected, inputs=inputs,
        scheduler=scheduler, prompts=prompts, service=service, principal=principal, run_id='run:finite-visible')
    try:
        yield f
    finally:
        store.close()


def original_rows(f, kind):
    return list(f.store.iter_records(run_id=f.run_id, kinds=(kind,)))


async def readonly_status(f):
    # Complete SQLite original capture, including raw-file entries not JSON records.
    with f.store._lock:
        before = tuple(f.store.connection.iterdump())
        changes = f.store.connection.total_changes
    calls = len(f.prompts)
    def forbidden(*args, **kwargs):
        raise AssertionError('Status must not qualify or query current eligibility')
    qualify = f.owner.qualify if f.owner is not None else None
    eligible = f.owner.library.eligible_association if f.owner is not None else None
    if f.owner is not None:
        f.owner.qualify = forbidden
        f.owner.library.eligible_association = forbidden
    try:
        value = await f.service.get(f.principal, f.run_id)
        return value
    finally:
        if f.owner is not None:
            f.owner.qualify = qualify
            f.owner.library.eligible_association = eligible
        with f.store._lock:
            assert tuple(f.store.connection.iterdump()) == before
            assert f.store.connection.total_changes == changes
        assert len(f.prompts) == calls


def rewrite_original(f, envelope, **changes):
    # Adversarial original capture corruption; preserve its recorded index scope.
    original = copy.deepcopy(envelope['record'])
    changed = dict(original, **changes)
    digest = f.store.blobs.put(json_bytes(changed))
    with f.store.transaction() as db:
        db.execute('UPDATE artifacts SET sha256=? WHERE id=?', (digest, envelope['ref']['id']))
    return original


@pytest.mark.asyncio
async def test_status_stage_actual_single_node_history_needs_no_current_owner(tmp_path):
    async with stage_fixture(tmp_path) as f:
        result = await f.owner.execute(f.run_id, f.protected, scheduler=f.scheduler)
        assert result['status'] == 'completed'
        assert len(f.prompts) == 3 and len(f.store.accepted_outputs(f.run_id, 'screening')) == 2
        assert len(original_rows(f, 'dispatch-start')) == len(original_rows(f, 'dispatch-record')) == 1
        f.service.finite_e1 = f.service.profiles = f.service.model = f.service.scheduler = f.service.binder = None
        f.service._workspaces.clear()
        status = await readonly_status(f)
        assert status['stage'] == 'screening'
        assert status['node_statuses'] == [{'node_id':'screening','attempt_id':'screening-a1',
            'lifecycle_status':'Completed','skipped_because':None}]


@pytest.mark.asyncio
async def test_status_stage_real_finite_freeze_pending_placeholders_are_not_execution(tmp_path, monkeypatch):
    async with stage_fixture(tmp_path, segment=True) as f:
        async def interrupt_before_first_dispatch(*args, **kwargs):
            assert {n['state'] for n in f.store.node_states(f.run_id)} == {'pending'}
            assert not original_rows(f, 'dispatch-start')
            raise ResearchError('controlled_before_dispatch', 'Actual frozen plan interrupted before any start')
        # The current runner starts prepared attempts, rather than using the
        # historical authorize_dispatch entry point. Stop the real workflow
        # before its first callback so all frozen nodes are still pending.
        monkeypatch.setattr('jiuwenswarm.research.scheduler.run_native_workflow', interrupt_before_first_dispatch)
        with pytest.raises(ResearchError, match='controlled_before_dispatch'):
            await f.owner.execute(f.run_id, f.protected, scheduler=f.scheduler)
        bindings=original_rows(f,'finite-e1-plan-binding')
        assert len(bindings)==1 and bindings[0]['record']['run_id']==f.run_id
        plan_ref=bindings[0]['record']['plan_ref']
        assert f.store.record_kind(plan_ref)=='run-plan'
        plan=f.store.read_record(plan_ref,contract_id='run-plan')
        assert plan['frozen'] is True and {n['node_id'] for n in plan['nodes']}=={'screening','hypothesis'}
        assert len(original_rows(f, 'finite-e1-fixture-qualification')) == 1
        assert not f.prompts and not original_rows(f, 'dispatch-start')
        assert not original_rows(f, 'gate-decision') and not original_rows(f, 'acceptance-commit')
        assert {n['node_id'] for n in f.store.node_states(f.run_id)} == {'screening','hypothesis'}
        status = await readonly_status(f)
        assert status['stage'] == ''
        assert {n['lifecycle_status'] for n in status['node_statuses']} == {'Pending'}
        assert status['status'] == 'halted' and status['reasons'] == ['protected_stop']


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['missing_start','foreign_start_run','foreign_start_node','start_attempt',
    'dispatch_attempt','dispatch_plan','dispatch_parent','commit_attempt','commit_id','missing_node_gate','ambiguous_active'])
async def test_status_stage_corrupt_original_chronology_is_unavailable_without_read_effects(tmp_path, fault):
    async with stage_fixture(tmp_path, segment=fault=='ambiguous_active') as f:
        result = await f.owner.execute(f.run_id, f.protected, scheduler=f.scheduler)
        assert result['status'] == 'completed'
        start = next(e for e in original_rows(f, 'dispatch-start') if e['record']['node_id']=='screening')
        dispatch = next(e for e in original_rows(f, 'dispatch-record') if e['record']['node_id']=='screening')
        if fault == 'missing_start':
            with f.store.transaction() as db: db.execute('DELETE FROM records WHERE id=?',(start['ref']['id'],))
        elif fault == 'foreign_start_run': rewrite_original(f, start, run_id='run:foreign')
        elif fault == 'foreign_start_node': rewrite_original(f, start, node_id='foreign')
        elif fault == 'start_attempt':
            parent = f.store.read_record(start['record']['node_contract_ref'], contract_id='node-execution-contract')
            changed = dict(parent, id='foreign_'+parent['id'], attempt_id='screening-a9')
            ref = f.store.put_record('node-execution-contract', changed, scope=changed)
            rewrite_original(f, start, node_contract_ref=ref)
        elif fault == 'dispatch_attempt': rewrite_original(f, dispatch, attempt_id='screening-a9')
        elif fault == 'dispatch_plan': rewrite_original(f, dispatch, run_plan_ref=f.protected['configuration_ref'])
        elif fault == 'dispatch_parent': rewrite_original(f, dispatch, node_contract_ref=f.protected['configuration_ref'])
        elif fault in {'commit_attempt','commit_id'}:
            column = 'attempt_id' if fault == 'commit_attempt' else 'commit_id'
            with f.store.transaction() as db:
                db.execute('UPDATE acceptance SET '+column+'=? WHERE run_id=? AND node_id=? AND subnode_id=?',
                    ('foreign-original-identity',f.run_id,'screening',''))
        elif fault == 'missing_node_gate':
            gates=[e for e in original_rows(f,'gate-decision') if e['record']['scope_kind']=='node']
            assert gates
            with f.store.transaction() as db: db.execute('DELETE FROM records WHERE id=?',(gates[0]['ref']['id'],))
        else:
            assert {e['record']['node_id'] for e in original_rows(f,'dispatch-start')} == {'screening','hypothesis'}
            with f.store.transaction() as db:
                db.execute("UPDATE nodes SET state='running' WHERE run_id=?",(f.run_id,))
        with pytest.raises(ResearchError) as error:
            await readonly_status(f)
        assert error.value.code == 'unavailable'


@pytest.mark.asyncio
async def test_status_stage_genuine_ordinary_compiler_preplan_history_is_preserved(tmp_path, monkeypatch):
    # Reuse the established actual Compiler/Factory/Runner/check/Gate/commit
    # positive, adding the original request ID at allocation for status scope.
    from tests.unit_tests.research.test_compiler import test_compiler_requires_internal_acceptance_and_commits_one_external_brief
    captured = []
    create = SQLiteRunStore.create_run
    def create_with_request(self, run_id, *, account_id, workspace_id, submission):
        # This established fixture pins protected configuration to the same original
        # opaque Ref as intake.profile_ref (test_compiler.py79-81), at allocation.
        exact_configuration = self.read_record(submission['intake_ref'])['profile_ref']
        submission = dict(submission, client_request_id='ordinary-stage-original-request',
                          configuration_ref=exact_configuration)
        captured.append(self)
        return create(self, run_id, account_id=account_id, workspace_id=workspace_id, submission=submission)
    monkeypatch.setattr(SQLiteRunStore, 'create_run', create_with_request)
    await test_compiler_requires_internal_acceptance_and_commits_one_external_brief(tmp_path,None,'fixed_baseline')
    assert len(captured) == 1
    store = captured[0]
    try:
        dispatches = list(store.iter_records(run_id='run:compiler', kinds=('dispatch-record',)))
        assert len(dispatches)==1 and dispatches[0]['record']['phase']=='pre_plan'
        assert dispatches[0]['record']['run_plan_ref'] is None
        assert store.accepted_outputs('run:compiler','intention_compiler')
        assert not list(store.iter_records(kinds=('run-plan',)))
        assert not list(store.iter_records(run_id='run:compiler', kinds=('finite-e1-plan-binding','finite-e1-fixture-qualification','finite-e1-run-selection')))
        service=ResearchService(store,registry=None,model=None)
        f=SimpleNamespace(store=store,owner=None,prompts=[],service=service,run_id='run:compiler',
            principal=Principal('alice',frozenset({'project'}),frozenset({'status','reconcile'})))
        status = await readonly_status(f)
        assert status['stage']=='intention_compiler'
        assert status['node_statuses'][0]['lifecycle_status']=='Completed'
    finally:
        store.close()


@pytest.mark.asyncio
async def test_status_stage_real_allocated_segment_reconcile_retains_actual_last_node(tmp_path):
    async with stage_fixture(tmp_path, segment=True) as f:
        original = f.store.get_run(f.run_id)['submission']
        submission = copy.deepcopy(original)
        submission['client_request_id'] = 'chronology-authenticated-request'
        first = await f.service.submit(f.principal, submission)
        actual_run = first['run_id']
        assert actual_run != f.run_id  # Genuine service allocation, not preparation run.
        await f.service._tasks[actual_run]
        f.run_id = actual_run
        assert f.store.get_run(actual_run)['state'] == 'completed'
        assert len(f.prompts) == 5
        assert f.store.accepted_outputs(actual_run,'screening') and f.store.accepted_outputs(actual_run,'hypothesis')
        before = tuple(f.store.connection.iterdump())
        status = await readonly_status(f)
        assert await f.service.list(f.principal,client_request_id=submission['client_request_id']) == [status]
        assert tuple(f.store.connection.iterdump()) == before
        assert status['stage'] == 'hypothesis'
        assert not list(f.store.iter_records(run_id=actual_run,kinds=('dispatch-record',))) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('stopped_node',['screening','hypothesis'])
@pytest.mark.parametrize('stop',['paused_recovery','protected_halt','cancellation_pending'])
async def test_status_stage_stopped_open_attempt_history_keeps_prior_finished_or_absence(tmp_path,monkeypatch,stop,stopped_node):
    async with stage_fixture(tmp_path,segment=True) as f:
        transport=f.scheduler.runner.model.subscription
        invoke=transport.invoke_governed
        arrived=asyncio.Event(); release=asyncio.Event(); task=None; history=None
        async def held(prompt, *, model, timeout_s):
            payload=__import__('json').loads(prompt.split('<subject_payload>\n',1)[1].split('\n</subject_payload>',1)[0])
            verifier=set(payload)=={'subject_declaration','subject_output'}
            hypothesis='input_refs' in payload and 'opportunity' in payload
            if not verifier and (hypothesis if stopped_node=='hypothesis' else not hypothesis):
                arrived.set()
                await release.wait()
            return await invoke(prompt,model=model,timeout_s=timeout_s)
        monkeypatch.setattr(transport,'invoke_governed',held)
        try:
            submission=copy.deepcopy(f.store.get_run(f.run_id)['submission'])
            submission['client_request_id']='history-'+stop+'-'+stopped_node
            initial=await f.service.submit(f.principal,submission)
            f.run_id=initial['run_id'];task=f.service._tasks[f.run_id]
            await asyncio.wait_for(arrived.wait(),60)
            assert f.store.get_run(f.run_id)['state']=='running'
            assert {e['record']['node_id'] for e in original_rows(f,'dispatch-start')} == ({'screening'} if stopped_node=='screening' else {'screening','hypothesis'})
            assert not f.store.accepted_outputs(f.run_id,stopped_node)
            assert not any(e['record']['node_id']==stopped_node for e in original_rows(f,'dispatch-record'))
            assert len(f.prompts)==(0 if stopped_node=='screening' else 3)
            if stop=='paused_recovery':
                # Genuine durable open-attempt snapshot, then actual sole-owner
                # recovery on that copied store. No dispatch/state is fabricated.
                copied=tmp_path/'recovered-open-store'
                (copied/'state').mkdir(parents=True)
                shutil.copytree(f.store.root/'artifacts',copied/'artifacts')
                db=sqlite3.connect(copied/'state'/'research.sqlite3')
                with f.store._lock: f.store.connection.backup(db)
                db.close()
                history=SQLiteRunStore(copied,recover=True)
                run=history.get_run(f.run_id)
                assert run['state']=='paused' and run['reason']=='interrupted'
                with history._lock:
                    claims=history.connection.execute('SELECT state FROM attempts WHERE run_id=? AND node_id=?',(f.run_id,stopped_node)).fetchall()
                assert claims and all(row['state']=='paused' for row in claims)
            else:
                if stop=='cancellation_pending':
                    request=f.store.request_cancellation(f.run_id,'owner','actual-open-history-cancel')
                    assert request['status']=='requested'
                task.cancel()
                await asyncio.wait_for(asyncio.gather(task,return_exceptions=True),60)
                history=f.store
                run=history.get_run(f.run_id)
                assert run['state']=='halted' and run['reason']=='protected_stop'
                assert original_rows(f,'execution-cancelled-pending')
                if stop=='cancellation_pending':
                    assert history.get_cancellation(f.run_id,'actual-open-history-cancel')['status']=='requested'
                    assert not original_rows(f,'execution-contained')  # Never claim terminal containment.
            reader=ResearchService(history,registry=None,model=None)
            snapshot=SimpleNamespace(store=history,owner=None,prompts=[],service=reader,
                principal=f.principal,run_id=f.run_id)
            before_nodes=history.node_states(f.run_id)
            assert next(n for n in before_nodes if n['node_id']==stopped_node)['state']=='failed'
            interrupted = [e['record'] for e in history.iter_records(run_id=f.run_id,kinds=('dispatch-record',))
                           if e['record']['node_id']==stopped_node]
            assert len(interrupted)==1 and interrupted[0]['outcome']=='interrupted'
            assert interrupted[0]['ended_at'] is None and interrupted[0]['model_calls_used'] is None
            assert interrupted[0]['gate_decision_ref'] is None and interrupted[0]['output_refs']==[]
            if stop=='paused_recovery':
                assert interrupted[0]['elapsed_s'] is None
            assert not any(e['record']['node_id']==stopped_node and e['record']['subnode_id']==''
                for e in history.iter_records(run_id=f.run_id,kinds=('acceptance-commit',)))
            status=await readonly_status(snapshot)
            assert status['stage']==stopped_node
            assert status['status']==run['state'] and status['reasons']==[run['reason']]
            assert history.node_states(f.run_id)==before_nodes
            assert next(n for n in status['node_statuses'] if n['node_id']==stopped_node)['lifecycle_status']=='Failed'
            # The original start and interrupted record identify where work
            # stopped. They prove neither completion nor terminal containment.
        finally:
            if task is not None and not task.done(): task.cancel()
            release.set()
            if task is not None: await asyncio.wait_for(asyncio.gather(task,return_exceptions=True),60)
            if history is not None and history is not f.store: history.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['template_kind','dispatch_check_plan','dispatch_internal_inventory',
    'dispatch_cc','dispatch_check_pins','missing_state_attempt'])
async def test_status_stage_exact_original_template_dispatch_and_attempt_are_required(tmp_path,fault):
    async with stage_fixture(tmp_path) as f:
        result=await f.owner.execute(f.run_id,f.protected,scheduler=f.scheduler)
        assert result['status']=='completed' and len(f.prompts)==3
        start=original_rows(f,'dispatch-start')[0]
        dispatch=original_rows(f,'dispatch-record')[0]
        parent=f.store.read_record(start['record']['node_contract_ref'],contract_id='node-execution-contract')
        if fault=='template_kind':
            work=next(row for row in parent['subnodes'] if row['role']=='work')
            with f.store.transaction() as db:
                db.execute('UPDATE records SET kind=? WHERE id=?',('foreign-template-kind',work['template_ref']['id']))
        elif fault=='dispatch_check_plan':
            rewrite_original(f,dispatch,check_plan_ref=f.protected['configuration_ref'])
        elif fault=='dispatch_internal_inventory':
            assert dispatch['record']['output_gate_decision_refs']
            rewrite_original(f,dispatch,output_gate_decision_refs=[])
        elif fault=='dispatch_cc':
            changed=dict(dispatch['record']['cc'],cc_version='9.9.9')
            rewrite_original(f,dispatch,cc=changed)
        elif fault=='dispatch_check_pins':
            changed=dict(dispatch['record']['check_pins'])
            changed['checking_profile_sha256']='0'*64
            rewrite_original(f,dispatch,check_pins=changed)
        else:
            with f.store.transaction() as db:
                db.execute('UPDATE nodes SET attempt_id=NULL WHERE run_id=? AND node_id=?',(f.run_id,'screening'))
        with pytest.raises(ResearchError) as error:
            await readonly_status(f)
        assert error.value.code=='unavailable'


@pytest.mark.asyncio
async def test_status_stage_recovery_keeps_finished_sibling_and_paused_inflight_attempt(tmp_path,monkeypatch):
    async with stage_fixture(tmp_path) as f:
        transport=f.scheduler.runner.model.subscription;invoke=transport.invoke_governed
        arrived=asyncio.Event();release=asyncio.Event();review_count=0;task=None;history=None
        async def held(prompt,*,model,timeout_s):
            nonlocal review_count
            payload=__import__('json').loads(prompt.split('<subject_payload>\n',1)[1].split('\n</subject_payload>',1)[0])
            if set(payload)=={'subject_declaration','subject_output'}:
                review_count+=1
                if review_count==2:
                    arrived.set();await release.wait()
            return await invoke(prompt,model=model,timeout_s=timeout_s)
        monkeypatch.setattr(transport,'invoke_governed',held)
        try:
            submission=copy.deepcopy(f.store.get_run(f.run_id)['submission'])
            submission['client_request_id']='mixed-original-recovery'
            initial=await f.service.submit(f.principal,submission);f.run_id=initial['run_id'];task=f.service._tasks[f.run_id]
            await asyncio.wait_for(arrived.wait(),60)
            assert len(f.prompts)==2 and review_count==2
            with f.store._lock:
                before=f.store.connection.execute('SELECT subnode_id,state FROM attempts WHERE run_id=?',(f.run_id,)).fetchall()
            assert any(row['state']=='accepted' for row in before) and any(row['state']=='running' for row in before)
            copied=tmp_path/'recovered-mixed-store';(copied/'state').mkdir(parents=True)
            shutil.copytree(f.store.root/'artifacts',copied/'artifacts')
            db=sqlite3.connect(copied/'state/research.sqlite3')
            with f.store._lock:f.store.connection.backup(db)
            db.close();history=SQLiteRunStore(copied,recover=True)
            with history._lock:
                after=history.connection.execute('SELECT subnode_id,state FROM attempts WHERE run_id=?',(f.run_id,)).fetchall()
            assert any(row['state']=='accepted' for row in after) and any(row['state']=='paused' for row in after)
            assert not any(row['state']=='running' for row in after)
            assert history.get_run(f.run_id)['state']=='paused' and history.get_run(f.run_id)['reason']=='interrupted'
            assert not history.accepted_outputs(f.run_id,'screening')
            interrupted = list(history.iter_records(run_id=f.run_id,kinds=('dispatch-record',)))
            assert len(interrupted)==1 and interrupted[0]['record']['outcome']=='interrupted'
            assert interrupted[0]['record']['ended_at'] is None
            assert interrupted[0]['record']['output_refs']==[]
            reader=ResearchService(history,registry=None,model=None)
            snapshot=SimpleNamespace(store=history,owner=None,prompts=[],service=reader,principal=f.principal,run_id=f.run_id)
            status=await readonly_status(snapshot)
            assert status['stage']=='screening' and status['status']=='paused' and status['reasons']==['interrupted']
            assert status['node_statuses'][0]['lifecycle_status']=='Failed'
        finally:
            if task is not None and not task.done():task.cancel()
            release.set()
            if task is not None:await asyncio.wait_for(asyncio.gather(task,return_exceptions=True),60)
            if history is not None:history.close()


@pytest.mark.asyncio
async def test_status_stage_rejected_original_cannot_claim_failed_outcome_with_node_gate(tmp_path):
    async with stage_fixture(tmp_path,fault='invalid_score') as f:
        result=await f.owner.execute(f.run_id,f.protected,scheduler=f.scheduler)
        assert result['status']=='partial' and len(f.prompts)==1
        dispatch=original_rows(f,'dispatch-record')[0]
        assert dispatch['record']['outcome']=='rejected'
        assert dispatch['record']['gate_decision_ref'] is not None and dispatch['record']['output_gate_decision_refs']
        gate=f.store.read_record(dispatch['record']['gate_decision_ref'],contract_id='gate-decision')
        assert gate['scope_kind']=='node' and gate['action']!='advance'
        assert not f.store.accepted_outputs(f.run_id,'screening')
        rewrite_original(f,dispatch,outcome='failed')  # Schema-valid source-semantic corruption, no invented producer.
        with pytest.raises(ResearchError) as error:
            await readonly_status(f)
        assert error.value.code=='unavailable'


@pytest.mark.asyncio
async def test_status_stage_paused_original_child_must_match_exact_assigned_template(tmp_path,monkeypatch):
    async with stage_fixture(tmp_path) as f:
        transport=f.scheduler.runner.model.subscription;invoke=transport.invoke_governed
        arrived=asyncio.Event();release=asyncio.Event();task=None;history=None
        async def held(prompt,*,model,timeout_s):
            arrived.set();await release.wait()
            return await invoke(prompt,model=model,timeout_s=timeout_s)
        monkeypatch.setattr(transport,'invoke_governed',held)
        try:
            submission=copy.deepcopy(f.store.get_run(f.run_id)['submission'])
            submission['client_request_id']='paused-original-template-corruption'
            initial=await f.service.submit(f.principal,submission);f.run_id=initial['run_id'];task=f.service._tasks[f.run_id]
            await asyncio.wait_for(arrived.wait(),60)
            assert not f.prompts and original_rows(f,'dispatch-start')
            copied=tmp_path/'recovered-child-template-store';(copied/'state').mkdir(parents=True)
            shutil.copytree(f.store.root/'artifacts',copied/'artifacts')
            db=sqlite3.connect(copied/'state/research.sqlite3')
            with f.store._lock:f.store.connection.backup(db)
            db.close();history=SQLiteRunStore(copied,recover=True)
            with history._lock:
                claims=history.connection.execute('SELECT * FROM attempts WHERE run_id=?',(f.run_id,)).fetchall()
            assert len(claims)==1 and claims[0]['state']=='paused'
            original_ref=__import__('json').loads(claims[0]['contract_ref'])
            child=history.read_record(original_ref,contract_id='subnode-execution-contract')
            parent=history.read_record(child['node_contract_ref'],contract_id='node-execution-contract')
            assigned=next(row for row in parent['subnodes'] if row['subnode_id']==child['subnode_id'])
            another=next(row for row in parent['subnodes'] if row['template_ref']!=assigned['template_ref'])
            corrupted=dict(child,id='foreign_'+child['id'],template_ref=another['template_ref'])
            substitute=history.put_record('subnode-execution-contract',corrupted,scope=corrupted)
            assert history.record_kind(substitute)=='subnode-execution-contract'
            assert history.read_record(original_ref,contract_id='subnode-execution-contract')==child  # No old-Ref hash mismatch.
            with history.transaction() as db:
                db.execute('UPDATE attempts SET contract_ref=? WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?',
                    (json_bytes(substitute).decode(),f.run_id,child['node_id'],child['subnode_id'],child['attempt_id']))
            reader=ResearchService(history,registry=None,model=None)
            snapshot=SimpleNamespace(store=history,owner=None,prompts=[],service=reader,principal=f.principal,run_id=f.run_id)
            with pytest.raises(ResearchError) as error:
                await readonly_status(snapshot)
            assert error.value.code=='unavailable'
        finally:
            if task is not None and not task.done():task.cancel()
            release.set()
            if task is not None:await asyncio.wait_for(asyncio.gather(task,return_exceptions=True),60)
            if history is not None:history.close()


@pytest.mark.asyncio
async def test_status_stage_original_work_check_pins_must_match_rewired_frozen_plan(tmp_path):
    async with stage_fixture(tmp_path) as f:
        result=await f.owner.execute(f.run_id,f.protected,scheduler=f.scheduler)
        assert result['status']=='completed' and len(f.prompts)==3
        start=original_rows(f,'dispatch-start')[0];dispatch=original_rows(f,'dispatch-record')[0]
        parent=f.store.read_record(start['record']['node_contract_ref'],contract_id='node-execution-contract')
        original=f.store.read_record(start['record']['run_plan_ref'],contract_id='run-plan')
        original_node=next(node for node in original['nodes'] if node['node_id']=='screening')
        assert dispatch['record']['check_pins']==original_node['check_pins']
        work=next(row for row in parent['subnodes'] if row['role']=='work')
        template=f.store.read_record(work['template_ref'])
        assert template['checking_profile_ref']['sha256']==original_node['check_pins']['checking_profile_sha256']
        clone=copy.deepcopy(original);clone['id']='clone_'+start['record']['run_plan_ref']['sha256'][:24]
        changed=next(node for node in clone['nodes'] if node['node_id']=='screening')
        changed['check_pins']['checking_profile_sha256']='0'*64
        clone_ref=f.store.put_record('run-plan',clone)
        assert f.store.record_kind(clone_ref)=='run-plan' and clone['frozen'] is True
        assert clone['configuration_ref']==original['configuration_ref'] and clone['source_ref']==original['source_ref']
        assert clone['policy_ref']==original['policy_ref'] and changed['cc']==original_node['cc']
        rewrite_original(f,start,run_plan_ref=clone_ref)
        rewrite_original(f,dispatch,run_plan_ref=clone_ref,check_pins=changed['check_pins'])
        # Adversarial original-history corruption only: the clone never executes,
        # and no acceptance, parent assignment or real Gate/commit is fabricated.
        assert f.store.read_record(work['template_ref'])==template
        assert f.store.accepted_outputs(f.run_id,'screening')
        with pytest.raises(ResearchError) as error:
            await readonly_status(f)
        assert error.value.code=='unavailable'
