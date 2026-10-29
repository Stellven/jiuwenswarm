"""An approved slot still cannot substitute its pinned source/input semantics."""
import pytest

from jiuwenswarm.research.contracts import ResearchError
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime
from tests.unit_tests.research.test_evaluation_private_replay import replay_runtime
from tests.unit_tests.research.test_evaluation_replay import replay_fixture


@pytest.mark.asyncio
async def test_missing_registered_private_runtime_cannot_advertise_effect_entry_points(tmp_path):
    store, provider, _, _, _ = await source_fixture(tmp_path)
    try:
        assert provider.available_entry_points == ()
    finally:
        store.close()


@pytest.mark.asyncio
async def test_approved_single_slot_cannot_ignore_public_named_input_inventory(tmp_path):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        malformed = request | {'inputs': []}
        owner = provider.resources.bind_runtime(capture_runtime(store, provider, [malformed]))
        ref = owner.accept_request(actor, malformed, 'E3')
        with pytest.raises(ResearchError): owner.prepare(ref)
        assert not list(store.iter_records(kinds=('evaluation-assignment-grant',)))
        assert prompts == []
    finally:
        store.close()


@pytest.mark.asyncio
async def test_approved_replay_slot_cannot_ignore_original_node_identity(tmp_path):
    store, provider, actor, request, prompts, _ = await replay_fixture(tmp_path)
    try:
        malformed = request | {'node_id': 'other-node'}
        owner = provider.resources.bind_runtime(replay_runtime(store, provider, [malformed]))
        ref = owner.accept_request(actor, malformed, 'E2')
        with pytest.raises(ResearchError): owner.prepare(ref)
        assert not list(store.iter_records(kinds=('evaluation-assignment-grant',)))
        assert len(prompts) == 1
    finally:
        store.close()
