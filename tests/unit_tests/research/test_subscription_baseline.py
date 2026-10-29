"""Finite native-owner comparison checks; no live subscription inference."""
import json

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.subscription_baseline import SubscriptionBaseline, task_prompt


class Subscription:
    def __init__(self): self.calls = []
    async def status(self): return {'state': 'ready'}
    async def invoke_governed(self, prompt, **options):
        self.calls.append((prompt, options))
        assert options['model'] == 'gpt-6.1-sol' and options['reasoning_effort'] == 'medium'
        return {'text': '{"answer":7}', 'identity': {'requested': 'gpt-6.1-sol', 'effective': 'gpt-6.1-sol'},
            'usage': {}, 'provider_request_id': 'controlled', 'observed_runtime': True}


@pytest.mark.asyncio
async def test_baseline_replay_returns_original_without_a_second_model_call(tmp_path):
    store = SQLiteRunStore(tmp_path/'state'); subscription = Subscription()
    owner = SubscriptionBaseline(store, subscription)
    payload = {'request_id': 'component-001', 'model': 'gpt-6.1-sol', 'timeout_s': 30,
        'assignment': {'task': 'Return the supplied number as JSON', 'inputs': [{'number': 7}]}}
    try:
        first = await owner.invoke(payload)
        assert first == await owner.invoke(payload)
        assert len(subscription.calls) == 1 and first['status'] == 'completed'
        assert first['invalid_for_product'] is True
        changed = dict(payload, assignment={'task': 'different', 'inputs': [8]})
        with pytest.raises(ResearchError): await owner.invoke(changed)
        assert len(subscription.calls) == 1
        assert not list(store.iter_records(kinds=('model-call', 'gate-record')))
    finally:
        store.close()


def test_baseline_public_assignment_rejects_extra_reviewer_fields():
    with pytest.raises(ResearchError):
        task_prompt({'task': 'Answer', 'inputs': [1], 'expected_answer': 1})


def test_frozen_prompt_hash_matches_the_canonical_rpc_assignment():
    import hashlib
    from deploy.m1.chatgpt_baseline import canonical, prompt_sha256
    assignment = {'task': 'Return JSON', 'inputs': [{'z': 1, 'a': 2}]}
    transported = json.loads(canonical(assignment))
    assert prompt_sha256(assignment) == hashlib.sha256(task_prompt(transported).encode()).hexdigest()
