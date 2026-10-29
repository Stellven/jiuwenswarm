"""Actual protected native boundaries; controlled eligibility/replies are not live QA qualification.

The historical node_a_to_b population is still absent. These real finite_e1
cases implement only their named V12 increment and never imply full V12 PASS.
"""
import asyncio
import copy
import json

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_finite_e1 import finite_execution_fixture


def actual_event_node(store, envelope):
    value = envelope['record']
    if envelope['kind'] == 'model-call-start':
        # The original start names its protected child Ref, not a node_id field.
        child = store.read_record(value['contract_ref'], contract_id='subnode-execution-contract')
        assert child['run_id'] == value['run_id']
        return child['node_id']
    return value['node_id']


def actual_diagnostics(store, result=None):
    return {'result': result,
        'observations': [row['record'] for row in store.iter_records(kinds=('invocation-observation',))],
        'failed_checks': [item for row in store.iter_records(kinds=('deterministic-check-result',))
                          for item in row['record']['results'] if item['outcome'] != 'PASS']}


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['valid', 'invalid_score'])
async def test_finite_e1_segment_flow_uses_only_committed_opportunity(tmp_path, fault):
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, fault, segment=True)
    try:
        result = await owner.execute('run:finite-visible', protected, scheduler=scheduler)
        assert result['status'] == ('completed' if fault == 'valid' else 'partial'), actual_diagnostics(store, result)
        if fault == 'valid':
            card = store.accepted_outputs('run:finite-visible', 'screening')['opportunity_card']
            blueprint_ref = store.accepted_outputs('run:finite-visible', 'hypothesis')['blueprint']
            blueprint = store.read_record(blueprint_ref, contract_id='hypothesis-blueprint')
            assert blueprint['opportunity_ref'] == card and blueprint['brief_ref'] == inputs['brief']
            starts = [r['record'] for r in store.iter_records(kinds=('dispatch-start',)) if r['record']['node_id'] == 'hypothesis']
            assert len(starts) == 1
            assert next(item['ref'] for item in starts[0]['bound_input_refs'] if item['name'] == 'opportunity') == card
            committed = [row for row in starts[0]['predecessor_commits'] if row['port'] == 'opportunity_card']
            assert len(committed) == 1 and committed[0]['artifact_ref'] == card
            original_commit = store.read_record(store.record_ref(committed[0]['commit_id']))
            assert original_commit['run_id'] == 'run:finite-visible' and original_commit['subnode_id'] == ''
            assert original_commit['output_refs']['opportunity_card'] == card
            assert len(prompts) == 5 and len(list(store.iter_records(kinds=('verifier-assessment',)))) == 3
        else:
            states = {row['node_id']: row for row in store.node_states('run:finite-visible')}
            assert states['hypothesis']['state'] == 'skipped' and states['hypothesis']['reason'] == 'screening'
            assert len(prompts) == 1 and not store.accepted_outputs('run:finite-visible', 'screening')
            assert not any(actual_event_node(store, row) == 'hypothesis' for row in store.iter_records(kinds=('dispatch-start', 'invocation-observation')))
        assert not store.is_accepted(inputs['brief']) and not store.is_accepted(inputs['candidate_set'])
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', [False, True])
async def test_finite_e1_segment_real_hold_locks_successor_and_cancellation_prevents_late_commit(tmp_path, cancel):
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid', segment=True, injected_fault='hold')
    task = None
    try:
        task = asyncio.create_task(owner.execute('run:finite-visible', protected, scheduler=scheduler))
        async def wait_for_actual_hold():
            while not list(store.iter_records(kinds=('fault-injection',))):
                if task.done():
                    return await task
                await asyncio.sleep(.02)
        await asyncio.wait_for(wait_for_actual_hold(), 60)
        assert not store.accepted_outputs('run:finite-visible', 'screening')
        assert len(prompts) == 3
        assert not any(actual_event_node(store, row) == 'hypothesis' for row in store.iter_records(kinds=('dispatch-start', 'invocation-observation')))
        assert not any(row['record']['scope_kind'] == 'node' for row in store.iter_records(kinds=('gate-decision',)))
        if cancel:
            store.request_cancellation('run:finite-visible', 'owner', 'cancel:actual-held-segment')
            with pytest.raises(ResearchError):
                await task
            await asyncio.sleep(.05)
            assert not store.accepted_outputs('run:finite-visible', 'screening')
            assert not store.accepted_outputs('run:finite-visible', 'hypothesis') and len(prompts) == 3
            assert not any(row['record']['scope_kind'] == 'node' and row['record']['action'] == 'advance'
                           for row in store.iter_records(kinds=('gate-decision',)))
        else:
            result = await task
            assert result['status'] == 'completed', actual_diagnostics(store, result)
            card = store.accepted_outputs('run:finite-visible', 'screening')['opportunity_card']
            blueprint = store.read_record(store.accepted_outputs('run:finite-visible', 'hypothesis')['blueprint'])
            assert blueprint['opportunity_ref'] == card and len(prompts) == 5
        outcomes = list(store.iter_records(kinds=('fault-injection-outcome',)))
        assert len(outcomes) == 1 and outcomes[0]['record']['outcome'] == ('cancelled' if cancel else 'completed')
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        store.close()


async def concrete_screening_parent(tmp_path):
    from jiuwenswarm.research.compiler import input_port
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid')
    qualified = store.read_record(owner.qualify('run:finite-visible', protected))
    assert qualified['status'] == 'qualified'
    row = owner.library.get('research.screening', owner._profile['candidate_pins'][0]['cc_version'])
    declaration = store.read_record(row['declaration_ref'])
    refs = dict(inputs, screening_rubric=row['body_refs']['screening_rubric.json'])
    ports = [input_port(port['name'], port['schema_ref'], refs[port['name']]) for port in declaration['ports']['inputs']]
    outputs = [{'name': port['name'], 'contract_id': port['schema_ref'], 'version': scheduler.factory._version(port['schema_ref']), 'required': port['required']}
               for port in declaration['ports']['outputs']]
    parent_ref = scheduler.factory.prepare_parent('run:finite-visible', 'screening',
        [{'subnode_id': 'screening', 'cc': owner._profile['candidate_pins'][0], 'depends_on': []}], inputs=ports, outputs=outputs,
        objective='Independent pre-effect authority denial', requirement_ids=['requirement:ranking'],
        limits=protected['run_limits'], policy_ref=owner._binding['policy_ref'], configuration_ref=protected['configuration_ref'],
        template_ref=owner._binding['template_ref'], authority_ceiling=copy.deepcopy(protected['authority_ceiling']))
    return store, owner, protected, scheduler, prompts, parent_ref, ports


@pytest.mark.asyncio
async def test_finite_e1_external_input_outside_parent_ceiling_rejects_before_binding_or_effect(tmp_path):
    store, owner, protected, scheduler, prompts, original, ports = await concrete_screening_parent(tmp_path)
    try:
        parent = store.read_record(original)
        parent.update(id='node:excluding-external')
        parent['authority_ceiling']['resource_reads'] = []
        parent_ref = store.put_record('node-execution-contract', parent)
        with pytest.raises(ResearchError):
            scheduler.factory.bind_subnode(parent_ref, 'screening', ports, role='work')
        assert not prompts and not list(store.iter_records(kinds=('invocation-observation', 'model-call-start', 'invocation-budget-reservation')))
    finally:
        store.close()


@pytest.mark.asyncio
async def test_finite_e1_forged_child_read_scope_rejects_before_real_worker_or_model(tmp_path):
    store, owner, protected, scheduler, prompts, original, ports = await concrete_screening_parent(tmp_path)
    try:
        child_ref, check_ref, bundle = scheduler.factory.bind_subnode(original, 'screening', ports, role='work')
        parent = store.read_record(original)
        parent.update(id='node:forged-parent')
        parent['authority_ceiling']['resource_reads'] = []
        parent_ref = store.put_record('node-execution-contract', parent)
        child = store.read_record(child_ref)
        child.update(id='subnode:forged-read-scope', node_contract_ref=parent_ref)
        forged = store.put_record('subnode-execution-contract', child)
        plan = store.read_record(check_ref)
        plan.update(id='check_plan:forged-read-scope', contract_ref=forged, node_contract_ref=parent_ref)
        check_ref = store.put_record('bound-check-plan', plan)
        scheduler.runner.configure_run('run:finite-visible',
            **{key: protected[key] for key in ('model_selection_profile_ref', 'deployment_ref', 'router', 'configuration_ref', 'run_limits')})
        with pytest.raises(ResearchError):
            await scheduler.runner.run(forged, check_ref, bundle_id=bundle)
        assert not prompts and not list(store.iter_records(kinds=('invocation-observation', 'model-call-start', 'invocation-budget-reservation')))
    finally:
        store.close()


@pytest.mark.asyncio
async def test_finite_e1_tampered_future_acceptance_row_never_releases_worker(tmp_path, monkeypatch):
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid', segment=True)
    original = scheduler.runner.capture_dispatch
    try:
        def capture(*args, **kwargs):
            result = original(*args, **kwargs)
            parent = store.read_record(args[0])
            if parent['node_id'] == 'screening':
                card = store.read_record(store.accepted_outputs('run:finite-visible', 'screening')['opportunity_card'])
                card['title'] = 'Foreign bytes outside the original immutable predecessor commit'
                foreign = store.put_blob(json_bytes(card))
                with store.transaction() as db:
                    db.execute("UPDATE acceptance SET artifact_ref=? WHERE run_id=? AND node_id=? AND subnode_id='' AND port=?",
                        (json_bytes(foreign).decode(), 'run:finite-visible', 'screening', 'opportunity_card'))
            return result
        monkeypatch.setattr(scheduler.runner, 'capture_dispatch', capture)
        with pytest.raises(ResearchError):
            await owner.execute('run:finite-visible', protected, scheduler=scheduler)
        assert len(prompts) == 3
        assert not any(actual_event_node(store, row) == 'hypothesis' for row in store.iter_records(kinds=('invocation-observation', 'model-call-start', 'dispatch-start')))
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('column', ['commit_id', 'attempt_id'])
async def test_finite_e1_tampered_future_row_identity_rejects_before_successor(tmp_path, monkeypatch, column):
    from jiuwenswarm.research.binding import committed_output_proof
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid', segment=True)
    original = scheduler.runner.capture_dispatch
    examined = []
    try:
        def capture(*args, **kwargs):
            result = original(*args, **kwargs)
            parent = store.read_record(args[0])
            if parent['node_id'] == 'screening':
                before = committed_output_proof(store, 'run:finite-visible', 'screening')
                original_receipt = store.read_record(before['receipt_ref'])
                original_gates = [store.read_record(ref) for ref in original_receipt['gate_decision_refs']]
                accepted = store.accepted_outputs('run:finite-visible', 'screening')
                # Mutate only a bounded indexed identity column. All immutable
                # original output bytes, receipt and actual Gate evidence remain.
                with store.transaction() as db:
                    db.execute('UPDATE acceptance SET ' + column + "=? WHERE run_id=? AND node_id=? AND subnode_id='' AND port=?",
                        ('forged:index-only-' + column, 'run:finite-visible', 'screening', 'opportunity_card'))
                assert store.accepted_outputs('run:finite-visible', 'screening') == accepted
                assert store.read_record(before['receipt_ref']) == original_receipt
                assert [store.read_record(ref) for ref in original_receipt['gate_decision_refs']] == original_gates
                with pytest.raises(ResearchError) as caught:
                    committed_output_proof(store, 'run:finite-visible', 'screening')
                assert caught.value.code == 'unaccepted_input'
                examined.append(column)
                raise ResearchError('test_boundary_observed', 'Stop after observing actual pre-successor identity rejection')
            return result
        monkeypatch.setattr(scheduler.runner, 'capture_dispatch', capture)
        with pytest.raises(ResearchError) as caught:
            await owner.execute('run:finite-visible', protected, scheduler=scheduler)
        assert caught.value.code == 'test_boundary_observed' and examined == [column]
        assert len(prompts) == 3
        assert not any(actual_event_node(store, row) == 'hypothesis' for row in store.iter_records(kinds=('invocation-observation', 'model-call-start', 'dispatch-start')))
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('scope', ['pair', 'node'])
async def test_finite_e1_acknowledged_cancellation_before_actual_commit_prevents_late_acceptance(tmp_path, monkeypatch, scope):
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid')
    original = store.put_record
    triggered = []
    try:
        def capture(contract_id, record, **kwargs):
            ref = original(contract_id, record, **kwargs)
            target = record.get('scope_kind') == 'node' if scope == 'node' else record.get('scope_kind') == 'subnode' and record.get('output_port') == 'opportunity_card'
            if contract_id == 'gate-decision' and target and record.get('action') == 'advance' and not triggered:
                # Persist the genuine advancing Gate first, then acknowledge a
                # real cancellation before the ordinary Store commit executes.
                triggered.append(store.request_cancellation('run:finite-visible', 'owner', 'cancel:before-real-' + scope))
            return ref
        monkeypatch.setattr(store, 'put_record', capture)
        with pytest.raises(ResearchError):
            await owner.execute('run:finite-visible', protected, scheduler=scheduler)
        assert len(triggered) == 1 and len(prompts) == 3
        subnode = 'screening' if scope == 'pair' else ''
        assert not store.accepted_outputs('run:finite-visible', 'screening', subnode_id=subnode)
        assert not any(row['record']['subnode_id'] == subnode for row in store.iter_records(kinds=('acceptance-commit',)))
    finally:
        store.close()


@pytest.mark.asyncio
async def test_finite_e1_prepared_host_ref_outside_base_rejects_before_effect(tmp_path):
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid')
    try:
        rubric = protected['host_records']['screening_rubric']
        protected['authority_ceiling']['resource_reads'] = [ref for ref in protected['authority_ceiling']['resource_reads'] if ref != rubric]
        failure = None
        result = None
        try:
            result = await owner.execute('run:finite-visible', protected, scheduler=scheduler)
        except ResearchError as error:
            failure = error
        assert failure is not None, actual_diagnostics(store, result)
        assert not prompts and not list(store.iter_records(kinds=('invocation-observation', 'model-call-start', 'invocation-budget-reservation')))
    finally:
        store.close()


async def rejects_before_new_claim_or_effect(store, scheduler, protected, child_ref, check_ref, bundle, prompts):
    scheduler.runner.configure_run('run:finite-visible',
        **{key: protected[key] for key in ('model_selection_profile_ref', 'deployment_ref', 'router', 'configuration_ref', 'run_limits')})
    failure = None
    try:
        await scheduler.runner.run(child_ref, check_ref, bundle_id=bundle)
    except ResearchError as error:
        failure = error
    assert failure is not None, actual_diagnostics(store)
    with store._lock:
        attempts = store.connection.execute('SELECT * FROM attempts WHERE run_id=?', ('run:finite-visible',)).fetchall()
    assert not attempts, 'A malformed original child obtained a durable attempt claim before refusal'
    assert not prompts and not list(store.iter_records(kinds=('invocation-observation', 'model-call-start', 'invocation-budget-reservation')))


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['tools', 'write_roots'])
async def test_finite_e1_factory_narrows_parent_union_to_selected_declaration(tmp_path, field):
    store, owner, protected, scheduler, prompts, original, ports = await concrete_screening_parent(tmp_path)
    try:
        parent = store.read_record(original)
        parent.update(id='node:parent-union-' + field)
        parent['authority_ceiling'][field] = ['deepsearch'] if field == 'tools' else ['/workspace/poc']
        parent_ref = store.put_record('node-execution-contract', parent)
        child_ref, _, _ = scheduler.factory.bind_subnode(parent_ref, 'screening', ports, role='work')
        child = store.read_record(child_ref)
        assert child['bindings'][0]['effective_authority'][field] == [], 'Screening borrowed a sibling tool/workspace from its parent union'
        assert not prompts and not list(store.iter_records(kinds=('invocation-observation', 'model-call-start', 'invocation-budget-reservation')))
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['tools', 'write_roots'])
async def test_finite_e1_forged_parent_union_effect_rejects_before_claim(tmp_path, field):
    store, owner, protected, scheduler, prompts, original, ports = await concrete_screening_parent(tmp_path)
    try:
        parent = store.read_record(original)
        parent.update(id='node:forged-union-' + field)
        grant = ['deepsearch'] if field == 'tools' else ['/workspace/poc']
        parent['authority_ceiling'][field] = grant
        parent_ref = store.put_record('node-execution-contract', parent)
        child_ref, check_ref, bundle = scheduler.factory.bind_subnode(parent_ref, 'screening', ports, role='work')
        child = store.read_record(child_ref)
        child.update(id='subnode:forged-union-' + field)
        child['bindings'][0]['effective_authority'][field] = grant
        forged = store.put_record('subnode-execution-contract', child)
        plan = store.read_record(check_ref)
        plan.update(id='check_plan:forged-union-' + field, contract_ref=forged)
        check_ref = store.put_record('bound-check-plan', plan)
        await rejects_before_new_claim_or_effect(store, scheduler, protected, forged, check_ref, bundle, prompts)
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['limit_time', 'limit_calls', 'limit_memory', 'admission', 'implementation_swap', 'implementation_missing', 'dependency_extra', 'dependency_missing', 'template', 'declaration'])
async def test_finite_e1_forged_child_pin_or_limit_rejects_before_claim(tmp_path, fault):
    store, owner, protected, scheduler, prompts, original, ports = await concrete_screening_parent(tmp_path)
    try:
        child_ref, check_ref, bundle = scheduler.factory.bind_subnode(original, 'screening', ports, role='work')
        child = store.read_record(child_ref)
        child.update(id='subnode:forged-' + fault)
        binding = child['bindings'][0]
        if fault.startswith('limit_'):
            key = {'limit_time': 'time_s', 'limit_calls': 'model_calls', 'limit_memory': 'memory_mb'}[fault]
            child['subnode_limits'][key] += 1
            binding['limits'][key] = child['subnode_limits'][key]
        elif fault == 'admission':
            verifier = store.read_record(owner._profile['verifier_cc_ref'])['identity']
            binding['admission_ref'] = owner.library.get(verifier['name'], verifier['version_label'])['admission_ref']
        elif fault == 'implementation_swap':
            assert binding['implementation_refs']
            binding['implementation_refs'][0] = store.put_blob(b'foreign implementation outside original declaration')
        elif fault == 'implementation_missing':
            assert binding['implementation_refs']
            binding['implementation_refs'].pop()
        elif fault == 'dependency_extra':
            binding['dependency_refs'].append(store.put_blob(b'extra dependency absent from original declaration'))
        elif fault == 'dependency_missing':
            assert binding['dependency_refs'], 'The real installed Screening pins shared serialization; do not fabricate a missing dependency'
            binding['dependency_refs'].pop()
        elif fault == 'template':
            child['template_ref'] = store.put_blob(b'foreign unassigned template')
        else:
            binding['declaration_ref'] = owner._profile['verifier_cc_ref']
        forged = store.put_record('subnode-execution-contract', child)
        plan = store.read_record(check_ref)
        plan.update(id='check_plan:forged-' + fault, contract_ref=forged)
        check_ref = store.put_record('bound-check-plan', plan)
        await rejects_before_new_claim_or_effect(store, scheduler, protected, forged, check_ref, bundle, prompts)
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['output_schema', 'required_outputs', 'binding_lower', 'dependency_digest'])
async def test_finite_e1_refined_original_pin_rejects_before_claim(tmp_path, fault):
    store, owner, protected, scheduler, prompts, original, ports = await concrete_screening_parent(tmp_path)
    try:
        child_ref, check_ref, bundle = scheduler.factory.bind_subnode(original, 'screening', ports, role='work')
        child = store.read_record(child_ref)
        child.update(id='subnode:refined-' + fault)
        if fault == 'output_schema':
            child['outputs'][0]['contract_id'] = 'urn:jiuwenswarm:m1-design:research-brief:2.0.0'
            child['outputs'][0]['version'] = '2.0.0'
        elif fault == 'required_outputs':
            assert len(child['required_outputs']) == 2
            child['required_outputs'].pop()
        elif fault == 'binding_lower':
            assert child['bindings'][0]['limits'] == child['subnode_limits']
            child['bindings'][0]['limits']['time_s'] -= 1
        else:
            parent = store.read_record(original)
            template = store.read_record(child['template_ref'])
            declared = store.read_record(child['bindings'][0]['declaration_ref'])
            dependency = next(row['pin'] for row in declared['needs']['external'] if 'pin' in row)
            assert dependency['ref'] not in {row['path'] for row in declared['identity']['body']}
            prior = template['body_refs'][dependency['ref']]
            assert prior['sha256'] == dependency['sha256']
            foreign = store.put_blob(b'original-template metadata contradicts the unchanged declared dependency digest')
            template['body_refs'][dependency['ref']] = foreign
            template.update(id='template:contradictory-dependency')
            template_ref = store.append_record('subnode-template', template)
            next(row for row in parent['subnodes'] if row['subnode_id'] == 'screening')['template_ref'] = template_ref
            parent.update(id='node:contradictory-dependency')
            child['node_contract_ref'] = store.put_record('node-execution-contract', parent)
            child['template_ref'] = template_ref
            child['bindings'][0]['dependency_refs'] = [foreign if ref == prior else ref for ref in child['bindings'][0]['dependency_refs']]
            # The original candidate/body/admission/declaration are unchanged;
            # only the captured template dependency metadata contradicts CodePin.
            assert child['bindings'][0]['admission_ref'] == template['admission_ref']
        forged = store.put_record('subnode-execution-contract', child)
        plan = store.read_record(check_ref)
        plan.update(id='check_plan:refined-' + fault, contract_ref=forged, node_contract_ref=child['node_contract_ref'])
        check_ref = store.put_record('bound-check-plan', plan)
        await rejects_before_new_claim_or_effect(store, scheduler, protected, forged, check_ref, bundle, prompts)
    finally:
        store.close()


# Chronology controls are a separate follow-up to immutable authority/segment30.
# They execute the real installed segment and inspect authenticated read-only status.
@pytest.mark.asyncio
async def test_finite_e1_status_stage_tracks_actual_hypothesis_while_running(tmp_path, monkeypatch):
    from tests.unit_tests.research.test_status_stage import stage_fixture, readonly_status, original_rows
    async with stage_fixture(tmp_path, segment=True) as f:
        transport=f.scheduler.runner.model.subscription
        invoke=transport.invoke_governed
        arrived=asyncio.Event(); release=asyncio.Event(); task=None
        async def held(prompt, *, model, timeout_s):
            payload=json.loads(prompt.split('<subject_payload>\n',1)[1].split('\n</subject_payload>',1)[0])
            if 'input_refs' in payload and 'opportunity' in payload:
                arrived.set()
                await release.wait()
            return await invoke(prompt,model=model,timeout_s=timeout_s)
        monkeypatch.setattr(transport,'invoke_governed',held)
        try:
            task=asyncio.create_task(f.owner.execute(f.run_id,f.protected,scheduler=f.scheduler))
            await asyncio.wait_for(arrived.wait(),60)
            assert len(f.prompts)==3 and f.store.accepted_outputs(f.run_id,'screening')
            starts=original_rows(f,'dispatch-start')
            assert [e['record']['node_id'] for e in starts]==['screening','hypothesis']
            assert not f.store.accepted_outputs(f.run_id,'hypothesis')
            actual={n['node_id']:n for n in f.store.node_states(f.run_id)}
            assert actual['hypothesis']['state']=='running' and actual['screening']['state']=='completed'
            status=await readonly_status(f)
            assert status['stage']=='hypothesis'
            assert next(n for n in status['node_statuses'] if n['node_id']=='hypothesis')['lifecycle_status']=='Running'
        finally:
            release.set()
            if task is not None:
                await asyncio.wait_for(asyncio.gather(task,return_exceptions=True),60)


@pytest.mark.asyncio
async def test_finite_e1_status_stage_tracks_last_finished_hypothesis(tmp_path):
    from tests.unit_tests.research.test_status_stage import stage_fixture, readonly_status, original_rows
    async with stage_fixture(tmp_path,segment=True) as f:
        result=await f.owner.execute(f.run_id,f.protected,scheduler=f.scheduler)
        assert result['status']=='completed' and len(f.prompts)==5
        assert f.store.accepted_outputs(f.run_id,'screening') and f.store.accepted_outputs(f.run_id,'hypothesis')
        assert [e['record']['node_id'] for e in original_rows(f,'dispatch-record')]==['screening','hypothesis']
        assert [n['node_id'] for n in f.store.node_states(f.run_id)]==['hypothesis','screening']
        status=await readonly_status(f)
        assert status['stage']=='hypothesis'
        assert {n['lifecycle_status'] for n in status['node_statuses']}=={'Completed'}


@pytest.mark.asyncio
async def test_finite_e1_status_stage_ignores_skipped_unstarted_successor(tmp_path):
    from tests.unit_tests.research.test_status_stage import stage_fixture, readonly_status, original_rows
    async with stage_fixture(tmp_path,fault='invalid_score',segment=True) as f:
        result=await f.owner.execute(f.run_id,f.protected,scheduler=f.scheduler)
        assert result['status']=='partial' and len(f.prompts)==1
        assert not f.store.accepted_outputs(f.run_id,'screening') and not f.store.accepted_outputs(f.run_id,'hypothesis')
        assert [e['record']['node_id'] for e in original_rows(f,'dispatch-start')]==['screening']
        assert not original_rows(f,'verifier-assessment')
        status=await readonly_status(f)
        assert status['stage']=='screening'
        successor=next(n for n in status['node_statuses'] if n['node_id']=='hypothesis')
        assert successor['skipped_because']=='screening' and successor['attempt_id'] is None


@pytest.mark.asyncio
async def test_finite_e1_status_stage_uses_original_capture_order_when_utc_ties(tmp_path,monkeypatch):
    from jiuwenswarm.research import state,runner,scheduler
    from tests.unit_tests.research.test_status_stage import stage_fixture, readonly_status, original_rows
    async with stage_fixture(tmp_path,segment=True) as f:
        tied='2026-10-19T00:00:00Z'
        monkeypatch.setattr(state,'utc_now',lambda:tied)
        monkeypatch.setattr(runner,'utc_now',lambda:tied)
        monkeypatch.setattr(scheduler,'stamp',lambda:tied)
        result=await f.owner.execute(f.run_id,f.protected,scheduler=f.scheduler)
        assert result['status']=='completed' and len(f.prompts)==5
        starts=original_rows(f,'dispatch-start');ends=original_rows(f,'dispatch-record')
        assert [e['record']['node_id'] for e in starts]==['screening','hypothesis']
        assert [e['record']['node_id'] for e in ends]==['screening','hypothesis']
        assert {e['record']['recorded_at'] for e in starts}=={tied}
        assert {e['record']['started_at'] for e in ends}=={tied}
        assert {e['record']['ended_at'] for e in ends}=={tied}
        status=await readonly_status(f)
        assert status['stage']=='hypothesis'
