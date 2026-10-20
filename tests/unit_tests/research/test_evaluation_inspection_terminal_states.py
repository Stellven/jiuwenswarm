"""Original failed/unknown/cancelled proof10 states; controlled mechanics only."""
import json

import pytest

from tests.unit_tests.research.inspection_fixture import inspect_private
from tests.unit_tests.research.test_evaluation_executor_inspection import binding_of, closed, private_started
from tests.unit_tests.research.test_evaluation_failure_cleanup import failed_fixture


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['known', 'uncertain'])
async def test_private_inspector_preserves_actual_failure_and_containment_states(tmp_path, fault):
    store, provider, actor, request, prompts, owner = await failed_fixture(tmp_path, fault)
    try:
        result = await provider.single_cc(actor, request)
        assert result['status'] == ('failed' if fault == 'known' else 'blocked')
        assert result['reason'] == ('provider_error' if fault == 'known' else 'containment_uncertain')
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        request_ref = json.loads(row['request_ref'])
        terminal = owner.inspect(request_ref)
        assert terminal['state'] == ('failed' if fault == 'known' else 'outcome_unknown')
        assert bool(terminal['containment_ref']) == (fault == 'known')
        grant_ref = json.loads(store.connection.execute('SELECT grant_ref FROM evaluation_assignments').fetchone()[0])
        grant = store.read_record(grant_ref)
        prepared = (request_ref, grant['scope_ref'], grant_ref, grant)
        binding = binding_of(grant)
        publication = store.read_record(json.loads(row['head_ref']))
        assert publication['kind'] == 'terminal' and publication['capture_ref'] == json.loads(row['terminal_ref'])
        assert publication['previous_event_ref'] == terminal['through_event_ref']
        assert len(prompts) == 1 and terminal['measurement_refs']
        measurement_bytes = tuple(store.read_blob(ref) for ref in terminal['measurement_refs'])
        response = inspect_private(store, binding)
        closed(response, binding, prepared)
        assert response['state'] == terminal['state']
        assert response['terminal_ref'] == json.loads(row['terminal_ref'])
        assert response['containment_ref'] == terminal['containment_ref']
        assert response['cancel_id'] == row['cancel_id']
        owner.runner._evaluation_owners.clear()
        owner.runner.model = None
        owner.runner.executor = None
        provider.resources = None
        assert inspect_private(store, binding) == response
        assert tuple(store.read_blob(ref) for ref in terminal['measurement_refs']) == measurement_bytes
        assert len(prompts) == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_private_inspector_preserves_original_explicit_cancelled_assignment(tmp_path):
    store, provider, owner, prompts, prepared = await private_started(tmp_path)
    try:
        request_ref, scope_ref, grant_ref, grant = prepared[0]
        receipt = await owner.cancel(request_ref, 'cancel:i032-inspector-original')
        terminal = owner.inspect(request_ref)
        row = owner._row(request_ref)
        assert terminal['state'] == 'cancelled' and terminal['result_ref'] is None
        assert terminal['containment_ref'] == receipt['containment_ref']
        assert row['cancel_id'] == 'cancel:i032-inspector-original'
        assert len(prompts) == 0 and not owner.captures(request_ref, 'measurement')
        binding = binding_of(grant)
        response = inspect_private(store, binding)
        closed(response, binding, prepared[0])
        assert response['state'] == 'cancelled' and response['cancel_id'] == row['cancel_id']
        assert response['terminal_ref'] == json.loads(row['terminal_ref'])
        assert response['containment_ref'] == receipt['containment_ref']
        owner.runner._evaluation_owners.clear()
        assert inspect_private(store, binding) == response
        assert len(prompts) == 0
        # This is exact original private terminal/ack reconciliation only.
        # It establishes neither scientific kernel cessation nor lease release.
    finally:
        store.close()

