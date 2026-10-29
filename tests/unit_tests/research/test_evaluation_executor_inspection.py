"""Private IF016r2 proof10; no service/liveness/cessation qualification."""
import copy
import json
import time

import pytest

from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from tests.unit_tests.research.inspection_fixture import inspect_private
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime, product_state


async def private_started(root, *, second_slot=False, second_assignment=True):
    store, provider, actor, request, prompts = await source_fixture(root)
    requests = [request, request | {'request_id': request['request_id']+'-second'}] if second_slot else [request]
    owner = provider.resources.bind_runtime(capture_runtime(store, provider, requests))
    prepared = []
    for index, offered in enumerate(requests):
        req = owner.accept_request(actor, offered, 'E3'); scope = owner.prepare(req)
        if index and not second_assignment:
            # Real approved request/scope, with no conflicting assignment row.
            assert owner._row(req)['scope_ref'] == json_bytes(scope).decode()
            prepared.append((req, scope, None, None))
            continue
        ref = owner.prepare_assignment(scope, 'worker', None); grant = store.read_record(ref)
        assert store.record_kind(ref) == 'evaluation-assignment-grant'
        assert store.record_kind(grant['contract_ref']) == 'evaluation-subnode-context'
        assert grant['request_ref'] == req and grant['scope_ref'] == scope
        prepared.append((req, scope, ref, grant))
    context = owner.start_assignment(prepared[0][2], {})
    await owner.runner._await_start(context)
    assert context.execution_id == prepared[0][3]['execution_id'] and not prompts
    assert owner.runner._executions[context.execution_id]['closed'] is False
    return store, provider, owner, prompts, prepared


def binding_of(grant):
    return {k: copy.deepcopy(grant[k]) for k in ('contract_ref','invocation_id','execution_id')}


def closed(response, binding, prepared):
    assert set(response) == set(binding) | {'state','request_ref','scope_ref','assignment_grant_ref','terminal_ref','containment_ref','cancel_id'}
    assert all(response[k] == v for k,v in binding.items())
    assert response['request_ref'] == prepared[0] and response['scope_ref'] == prepared[1]
    assert response['assignment_grant_ref'] == prepared[2]


@pytest.mark.asyncio
async def test_executor_inspection_retains_published_terminal_after_owner_and_resource_loss(tmp_path):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        owner = provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
        before_product = product_state(store)
        assert (await provider.single_cc(actor, request))['status'] == 'completed' and len(prompts) == 1
        assert product_state(store) == before_product
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        grant_ref = json.loads(store.connection.execute('SELECT grant_ref FROM evaluation_assignments').fetchone()[0])
        grant = store.read_record(grant_ref); binding = binding_of(grant)
        prepared = (json.loads(row['request_ref']), grant['scope_ref'], grant_ref, grant)
        terminal_ref = json.loads(row['terminal_ref']); terminal = store.read_record(terminal_ref)
        validate('urn:ai4r:private:evaluation-terminal:1', terminal)
        assert terminal['request_ref'] == prepared[0] and terminal['state'] == 'completed'
        publication = store.read_record(json.loads(row['head_ref']))
        assert publication['kind'] == 'terminal' and publication['capture_ref'] == terminal_ref
        assert publication['previous_event_ref'] == terminal['through_event_ref']
        response = inspect_private(store, binding); closed(response, binding, prepared)
        assert response['state'] == 'completed' and response['terminal_ref'] == terminal_ref
        owner.runner._evaluation_owners.clear(); provider.resources = None
        assert inspect_private(store, binding) == response
        root = store.root; store.close(); store = SQLiteRunStore(root, recover=False)
        assert inspect_private(store, binding) == response and len(prompts) == 1
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['durable_only','stale_owner','expired_owner'])
async def test_executor_inspection_unknown_nonterminal_and_foreign_binding_never_supply_authority(tmp_path,fault):
    from jiuwenswarm.research.evaluation_authority import EvaluationAuthority
    store, provider, owner, prompts, prepared = await private_started(tmp_path)
    try:
        req, _, _, grant = prepared[0]; binding = binding_of(grant); raw = store.read_blob(req)
        live = inspect_private(store,binding,live_owner=owner); closed(live,binding,prepared[0])
        assert live['state'] == 'nonterminal' and live['terminal_ref'] is None
        if fault == 'stale_owner':
            owner.runner._evaluation_owners.remove(owner); EvaluationAuthority(provider.resources,owner.runtime_ref)
        elif fault == 'expired_owner':
            owner._deadlines[json_bytes(req).decode()] = time.monotonic()-1
            with pytest.raises(ResearchError): owner._active(req)
        response = inspect_private(store,binding,**({} if fault=='durable_only' else {'live_owner':owner}))
        closed(response,binding,prepared[0])
        assert response['state'] == 'outcome_unknown' and response['terminal_ref'] is None
        assert store.read_blob(req) == raw and not prompts
        with pytest.raises(ResearchError): inspect_private(store,binding|{'invocation_id':'foreign'})
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['request_ref','scope_ref','grant_ref'])
async def test_private_inspection_rejects_real_cross_request_assignment_index_swap(tmp_path,fault):
    store, _, owner, prompts, prepared = await private_started(tmp_path,second_slot=True,second_assignment=fault!='request_ref')
    try:
        first, second = prepared; binding = binding_of(first[3]); raw = store.read_blob(first[2])
        column = fault; foreign = second[0] if fault=='request_ref' else second[2]
        if fault == 'scope_ref':
            forged = copy.deepcopy(first[3]); forged.update(id=forged['id']+':scope-swap',scope_ref=second[1])
            validate('urn:ai4r:private:evaluation-assignment-grant:1',forged)
            foreign = store.append_record('evaluation-assignment-grant',forged); column = 'grant_ref'
        with store.transaction() as db:
            changed=db.execute('UPDATE evaluation_assignments SET '+column+'=? WHERE execution_id=?',
                               (json_bytes(foreign).decode(),binding['execution_id']))
            assert changed.rowcount == 1
        with pytest.raises(ResearchError): inspect_private(store,binding,live_owner=owner)
        assert store.read_blob(first[2]) == raw and not prompts
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['missing_publication_head','contradictory_terminal_row'])
async def test_private_inspection_refuses_terminal_object_without_exact_publication(tmp_path,fault):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        provider.resources.bind_runtime(capture_runtime(store,provider,[request]))
        assert (await provider.single_cc(actor,request))['status']=='completed' and len(prompts)==1
        row=store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        grant_ref=json.loads(store.connection.execute('SELECT grant_ref FROM evaluation_assignments').fetchone()[0])
        binding=binding_of(store.read_record(grant_ref)); pin=json.loads(row['terminal_ref'])
        terminal=store.read_record(pin); raw=store.read_blob(pin)
        assert store.read_record(json.loads(row['head_ref']))['capture_ref']==pin
        with store.transaction() as db:
            if fault=='missing_publication_head':
                db.execute('UPDATE evaluation_requests SET head_ref=?,sequence=? WHERE request_ref=?',
                           (json_bytes(terminal['through_event_ref']).decode(),row['sequence']-1,row['request_ref']))
            else: db.execute('UPDATE evaluation_requests SET terminal_ref=NULL WHERE request_ref=?',(row['request_ref'],))
        with pytest.raises(ResearchError): inspect_private(store,binding)
        assert store.read_blob(pin)==raw and len(prompts)==1
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('capability',[True,{'authorized':True}],ids=['boolean','mapping'])
async def test_private_inspection_rejects_caller_fabricated_live_capability(tmp_path,capability):
    store, _, _, prompts, prepared=await private_started(tmp_path)
    try:
        with pytest.raises(ResearchError): inspect_private(store,binding_of(prepared[0][3]),live_owner=capability)
        assert not prompts
    finally: store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['extra_field','foreign_execution','wrong_hash','canonical_source'])
async def test_private_inspection_requires_closed_original_private_binding(tmp_path,fault):
    store, _, _, prompts, prepared=await private_started(tmp_path)
    try:
        binding=binding_of(prepared[0][3])
        if fault=='extra_field': binding['authorized']=True
        elif fault=='foreign_execution': binding['execution_id']+=':foreign'
        elif fault=='wrong_hash': binding['contract_ref']['sha256']='0'*64
        else:
            binding['contract_ref']=store.read_record(binding['contract_ref'])['source_subject_ref']
            assert store.record_kind(binding['contract_ref'])=='subnode-execution-contract'
        with pytest.raises(ResearchError): inspect_private(store,binding)
        assert not prompts
    finally: store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', [
    'result_without_local_capture', 'failure_without_local_capture',
    'captured_foreign_measurement', 'captured_foreign_containment'])
async def test_private_inspector_rejects_actual_foreign_supporting_capture(tmp_path, fault):
    """Real second-slot captures, with an otherwise coherent negative journal.

    Opaque same-reason wrappers coherently recaptured by a trusted first journal
    are not distinguishable without new producer authority. This test never
    invents such authority: wrappers lack the first local edge, while the two
    deliberately recaptured bodies carry actual contradictory scope/context.
    """
    import uuid
    from jiuwenswarm.research.bridge import BridgeError
    from jiuwenswarm.research.evaluation_history import EvaluationReader

    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    class FailedTransport:
        async def invoke_governed(self, prompt, *, model, timeout_s):
            prompts.append(prompt)
            raise BridgeError('provider_error')
    provider.resources.admitted.runner.model.subscription = FailedTransport()
    requests = [request, request | {'request_id': request['request_id'] + '-second'}]
    owner = provider.resources.bind_runtime(capture_runtime(store, provider, requests))
    try:
        before_product = product_state(store)
        results = [await provider.single_cc(actor, offered) for offered in requests]
        assert all(result['status'] == 'failed' and result['reason'] == 'provider_error' for result in results)
        assert len(prompts) == 2 and product_state(store) == before_product
        rows = [store.connection.execute('SELECT * FROM evaluation_requests WHERE slot=?',
                    (slot['slot_id'],)).fetchone() for slot in owner.runtime['slots']]
        assert len(rows) == 2 and all(row['state'] == 'failed' for row in rows)
        assert rows[0]['cancel_id'] != rows[1]['cancel_id']
        refs = [json.loads(row['request_ref']) for row in rows]
        terminals = [owner.inspect(ref) for ref in refs]
        assert all(all(terminal[key] is not None for key in ('result_ref', 'failure_ref', 'containment_ref'))
                   and len(terminal['measurement_refs']) == 1 for terminal in terminals)
        for offered, result in zip(requests, results):
            assert provider.get(actor, offered['request_id'])['result'] == result
        grants = [store.connection.execute('SELECT grant_ref FROM evaluation_assignments WHERE request_ref=?',
                      (json_bytes(ref).decode(),)).fetchone()[0] for ref in refs]
        first_grant_ref = json.loads(grants[0])
        first_grant = store.read_record(first_grant_ref)
        binding = binding_of(first_grant)
        publication = store.read_record(json.loads(rows[0]['head_ref']))
        assert publication['kind'] == 'terminal'
        assert publication['previous_event_ref'] == terminals[0]['through_event_ref']
        reader = EvaluationReader(store, runtime_ref=owner.runtime_ref)
        _, original_chain = reader._journal(refs[0], dict(rows[0]), first_grant['scope_ref'])
        assert original_chain[-1][0] == json.loads(rows[0]['head_ref'])
        original_bytes = {json_bytes(ref).decode(): store.read_blob(ref)
            for terminal in terminals for ref in [terminal['result_ref'], terminal['failure_ref'],
                terminal['containment_ref'], *terminal['measurement_refs']]}
        original_bytes.update({json_bytes(ref).decode(): store.read_blob(ref)
            for ref, _ in original_chain})
        original_bytes.update({row['terminal_ref']: store.read_blob(json.loads(row['terminal_ref'])) for row in rows})

        field, capture_kind = {
            'result_without_local_capture': ('result_ref', 'result'),
            'failure_without_local_capture': ('failure_ref', 'failure'),
            'captured_foreign_measurement': ('measurement_refs', 'measurement'),
            'captured_foreign_containment': ('containment_ref', 'containment'),
        }[fault]
        foreign_ref = terminals[1][field][0] if field == 'measurement_refs' else terminals[1][field]
        assert foreign_ref != (terminals[0][field][0] if field == 'measurement_refs' else terminals[0][field])
        assert not any(event['capture_ref'] == foreign_ref for event in owner.captures(refs[0], capture_kind))
        forged = copy.deepcopy(terminals[0])
        forged['id'] = 'evaluation-terminal:foreign-' + uuid.uuid4().hex
        forged[field] = [foreign_ref] if field == 'measurement_refs' else foreign_ref
        head = copy.deepcopy(publication)
        head['id'] = 'evaluation-event:foreign-' + uuid.uuid4().hex
        if fault.startswith('captured_foreign_'):
            originals = owner.captures(refs[0], capture_kind)
            assert len(originals) == 1
            previous, replaced, copied_count = None, 0, 0
            for original_ref, original_event in original_chain[:-1]:
                assert original_event['kind'] != 'terminal'
                captured = copy.deepcopy(original_event)
                captured.update(id='evaluation-event:foreign-' + uuid.uuid4().hex,
                    previous_event_ref=previous)
                if (captured['kind'] == 'captured' and captured['capture_kind'] == capture_kind
                        and captured['capture_ref'] == originals[0]['capture_ref']):
                    captured['capture_ref'] = foreign_ref
                    replaced += 1
                validate('urn:ai4r:private:evaluation-event:1', captured)
                previous = store.append_record('evaluation-event', captured)
                copied_count += 1
            assert replaced == 1 and copied_count == len(original_chain) - 1
            forged['through_event_ref'] = previous
            head['previous_event_ref'] = previous
            # Replace one edge, rather than append a duplicate-kind shortcut.
            # Every original body/chain remains immutable negative evidence.
        forged['recorded_unix_ns'] = time.time_ns()
        validate('urn:ai4r:private:evaluation-terminal:1', forged)
        terminal_ref = store.append_record('evaluation-terminal', forged)
        head['capture_ref'] = terminal_ref
        head['recorded_unix_ns'] = time.time_ns()
        validate('urn:ai4r:private:evaluation-event:1', head)
        head_ref = store.append_record('evaluation-event', head)
        with store.transaction() as db:
            changed = db.execute('UPDATE evaluation_requests SET terminal_ref=?,head_ref=?,sequence=? WHERE request_ref=?',
                (json_bytes(terminal_ref).decode(), json_bytes(head_ref).decode(), head['sequence'], json_bytes(refs[0]).decode()))
            assert changed.rowcount == 1
        assert head['previous_event_ref'] == forged['through_event_ref']
        _, negative_chain = reader._journal(refs[0], dict(owner._row(refs[0])), first_grant['scope_ref'])
        assert len(negative_chain) == len(original_chain)
        assert sum(event['kind'] == 'captured' and event['capture_kind'] == capture_kind
                   for _, event in negative_chain) == sum(event['kind'] == 'captured'
                       and event['capture_kind'] == capture_kind for _, event in original_chain)
        if fault.startswith('captured_foreign_'):
            own_edges = [event for _, event in negative_chain
                if event['kind'] == 'captured' and event['capture_kind'] == capture_kind]
            assert len(own_edges) == 1 and own_edges[0]['capture_ref'] == foreign_ref
        with pytest.raises(ResearchError):
            inspect_private(store, binding)
        assert len(prompts) == 2 and product_state(store) == before_product
        assert all(store.read_blob(json.loads(key)) == raw for key, raw in original_bytes.items())
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['different_store_instance', 'closed_execution'])
async def test_private_inspector_requires_actual_same_live_instance(tmp_path, fault):
    store, _, owner, prompts, prepared = await private_started(tmp_path)
    other = None
    try:
        binding = binding_of(prepared[0][3])
        if fault == 'different_store_instance':
            other = SQLiteRunStore(store.root, recover=False)
            assert other is not store and owner.store is store
            assert other.read_blob(binding['contract_ref']) == store.read_blob(binding['contract_ref'])
            with pytest.raises(ResearchError):
                inspect_private(other, binding, live_owner=owner)
        else:
            owner.runner._executions[binding['execution_id']]['closed'] = True
            response = inspect_private(store, binding, live_owner=owner)
            closed(response, binding, prepared[0])
            assert response['state'] == 'outcome_unknown' and response['terminal_ref'] is None
        assert not prompts
    finally:
        if other is not None:
            other.close()
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['single', 'multi'])
async def test_e2_executor_inspection_retains_actual_failed_reviewer_after_resource_loss_and_reopen(tmp_path, monkeypatch, mode):
    """Keep every original cleanup assertion; add effect-free proof10 calls."""
    from jiuwenswarm.research.evaluation_authority import EvaluationAuthority
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    from tests.unit_tests.research.inspection_fixture import readonly_snapshot
    from tests.unit_tests.research.test_evaluation_e2_cleanup import (
        test_actual_e2_failed_review_cleanup_preserves_ordered_source_and_history as original_e2_case)

    actual_owner_inspect = EvaluationAuthority.inspect
    actual_reader_get = EvaluationReader.get
    phases, inspection_errors, first = [], [], {}

    def observe(store, request_ref, phase):
        # Only exact protected request-local rows supply the binding; no
        # invented terminal, grant, body, source port or inspection response.
        row = store.connection.execute('SELECT * FROM evaluation_requests WHERE request_ref=?',
            (json_bytes(request_ref).decode(),)).fetchone()
        assert row is not None and row['state'] == 'failed' and row['terminal_ref']
        grants = store.connection.execute('SELECT grant_ref FROM evaluation_assignments WHERE request_ref=?',
            (json_bytes(request_ref).decode(),)).fetchall()
        assert len(grants) == 1
        grant_ref = json.loads(grants[0]['grant_ref']); grant = store.read_record(grant_ref)
        scope_ref = json.loads(row['scope_ref']); scope = store.read_record(scope_ref)
        assert grant['role'] == 'verifier' and grant['scope_ref'] == scope_ref
        assert grant['request_ref'] == request_ref and grant['output_port'] == scope['selected_output_port']
        assert store.record_kind(grant['contract_ref']) == 'evaluation-subnode-context'
        terminal_ref = json.loads(row['terminal_ref']); terminal = store.read_record(terminal_ref)
        binding = binding_of(grant); captured_before = readonly_snapshot(store)
        try:
            response = inspect_private(store, binding)
            closed(response, binding, (request_ref, scope_ref, grant_ref, grant))
            assert response['state'] == 'failed' and response['terminal_ref'] == terminal_ref
            assert response['containment_ref'] == terminal['containment_ref'] and response['cancel_id'] == row['cancel_id']
            if 'response' in first:
                assert response == first['response']
            else:
                first['response'] = copy.deepcopy(response)
        except (AssertionError, ResearchError) as error:
            # Preserve every original cleanup/history assertion before
            # reporting an absent or incorrect new read-only helper.
            inspection_errors.append({'phase': phase, 'error': type(error).__name__, 'message': str(error)})
        finally:
            assert readonly_snapshot(store) == captured_before
        phases.append(phase)

    def observed_owner_inspect(owner, request_ref):
        value = actual_owner_inspect(owner, request_ref)
        if value.get('state') == 'failed' and value.get('result_ref') is not None:
            first.setdefault('store', owner.store)
            first.setdefault('root', owner.store.root)
            first.setdefault('request_ref', copy.deepcopy(request_ref))
            observe(owner.store, request_ref, 'published_owner')
        return value

    def observed_reader_get(reader, actor, request_id):
        value = actual_reader_get(reader, actor, request_id)
        if 'request_ref' in first and reader.store.root == first['root']:
            phase = 'same_store_history_after_resource_loss' if reader.store is first['store'] else 'reopened_history'
            observe(reader.store, first['request_ref'], phase)
        return value

    monkeypatch.setattr(EvaluationAuthority, 'inspect', observed_owner_inspect)
    monkeypatch.setattr(EvaluationReader, 'get', observed_reader_get)
    # Original actual-source producer/fault/containment/response assertions,
    # Source bytes/product eligibility, duplicate/resource-loss/reopen checks
    # and real closes execute without modification or intercepted failures.
    await original_e2_case(tmp_path, monkeypatch, mode)
    assert {'published_owner', 'same_store_history_after_resource_loss', 'reopened_history'} <= set(phases)
    assert not inspection_errors, 'E2 read-only inspector failed after all original assertions: ' + json.dumps(inspection_errors)
    assert 'response' in first
