"""Finite custody checks do not replace the live native owner authorizer."""
import copy
import json
import time

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime, product_state


@pytest.mark.asyncio
async def test_executor_custody_checks_exact_durable_owned_context_before_use(tmp_path):
    from jiuwenswarm.research.evaluation_authority import validate_evaluation_executor_binding
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        authority = provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
        before = product_state(store)
        req = authority.accept_request(actor, request, 'E3')
        scope = authority.prepare(req)
        grant_ref = authority.prepare_assignment(scope, 'worker', None)
        grant = store.read_record(grant_ref)
        child = store.read_record(grant['contract_ref'])
        context=authority.start_assignment(grant_ref, authority.runner._decode_inputs(child))
        await authority.runner._await_start(context)
        payload = {k: grant[k] for k in ('execution_id', 'invocation_id', 'contract_ref')}
        response = authority.authorize_executor_binding(payload)
        assert validate_evaluation_executor_binding(store, payload, response) == child
        for field, value in [('execution_id', 'foreign'), ('contract_ref', scope),
                             ('remaining_time_s', True), ('remaining_time_s', float('inf')),
                             ('execution_deadline_monotonic_s', time.monotonic() - 1)]:
            with pytest.raises(ResearchError):
                validate_evaluation_executor_binding(store, payload, response | {field: value})
        for field in ('schema', 'request_ref', 'node_contract_ref', 'bindings'):
            forged = copy.deepcopy(child)
            forged[field] = 'foreign' if field == 'schema' else scope if field != 'bindings' else []
            with pytest.raises(ResearchError):
                validate_evaluation_executor_binding(store, payload, response | {'contract': forged})
        encoded = lambda x: json_bytes(x).decode('utf-8')
        with store.transaction() as db:
            db.execute("UPDATE evaluation_requests SET cancel_id='actual-cancel' WHERE request_ref=?", (encoded(req),))
        with pytest.raises(ResearchError): validate_evaluation_executor_binding(store, payload, response)
        with store.transaction() as db:
            db.execute('UPDATE evaluation_requests SET cancel_id=NULL,deadline_ns=0 WHERE request_ref=?', (encoded(req),))
        with pytest.raises(ResearchError): validate_evaluation_executor_binding(store, payload, response)
        assert prompts == [] and before == product_state(store)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_executor_custody_refuses_prior_owner_after_reconstruction(tmp_path):
    from jiuwenswarm.research.evaluation_authority import EvaluationAuthority, validate_evaluation_executor_binding
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        authority = provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
        req = authority.accept_request(actor, request, 'E3')
        scope = authority.prepare(req)
        grant_ref = authority.prepare_assignment(scope, 'worker', None)
        grant = store.read_record(grant_ref)
        context=authority.start_assignment(grant_ref, authority.runner._decode_inputs(store.read_record(grant['contract_ref'])))
        await authority.runner._await_start(context)
        payload = {k: grant[k] for k in ('execution_id', 'invocation_id', 'contract_ref')}
        response = authority.authorize_executor_binding(payload)
        assert validate_evaluation_executor_binding(store, payload, response)['request_ref'] == req
        authority.runner._evaluation_owners.remove(authority)
        reopened = EvaluationAuthority(provider.resources, authority.runtime_ref)
        with pytest.raises(ResearchError): validate_evaluation_executor_binding(store, payload, response)
        with pytest.raises(ResearchError): authority.authorize_executor_binding(payload)
        with pytest.raises(ResearchError): reopened.authorize_executor_binding(payload)
        assert prompts == []
    finally:
        store.close()
