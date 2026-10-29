"""Immutable history composition refuses before registering another owner."""
import copy

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.evaluation_provider import InstalledEvaluationResources
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime, product_state


@pytest.mark.asyncio
async def test_replacement_runtime_pin_refuses_before_owner_boot_or_registration(tmp_path):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        resources = provider.resources
        first = capture_runtime(store, provider, [request])
        original_owner = resources.bind_runtime(first)
        runtime = copy.deepcopy(store.read_record(first))
        runtime['id'] += ':replacement'
        replacement_ref = store.append_record('evaluation-runtime', runtime)
        replacement = InstalledEvaluationResources(resources.admitted, profile_ref=provider.profile_ref,
            assets_ref=provider.assets_ref, library_snapshot_ref=resources.snapshot_ref)
        # Protected composition mistake, not a caller-controlled runtime field.
        provider.resources = replacement
        replacement.provider = provider
        runner = resources.admitted.runner
        before_boots = [tuple(row) for row in store.connection.execute('SELECT * FROM evaluation_owner_boots')]
        before_owners = set(runner._evaluation_owners)
        before_product = product_state(store)
        with pytest.raises(ResearchError):
            replacement.bind_runtime(replacement_ref)
        assert [tuple(row) for row in store.connection.execute('SELECT * FROM evaluation_owner_boots')] == before_boots
        assert set(runner._evaluation_owners) == before_owners == {original_owner}
        assert replacement.authority is None and provider._history_runtime_ref == first
        assert not prompts and product_state(store) == before_product
    finally:
        store.close()
