"""Provider disclosure is limited to visible material and bounded hypotheses."""
import asyncio
import json
import pytest

from jiuwenswarm.research_rsi.proposer import GuardedProposer,proposal_context
from jiuwenswarm.research_rsi.records import RecordStore


def test_context_uses_incumbent_and_bounded_history_without_protected_evidence():
    history=[{'sequence':i,'rationale':'hypothesis '+str(i),'attempt_status':'proposed',
        'visible_evidence_refs':[{'id':'visible'}],'queries_used':20,'stop_reason':'protected administrative diagnostic',
        'failure_evidence_refs':[{'id':'protected-path'}]} for i in range(1,9)]
    context=proposal_context({'diagnosis':'approved visible diagnosis'},body=b'def helper(): return 2\n',history=history,mutable_path='helper.py')
    assert context['authorized_mutable_path']=='helper.py'
    assert context['incumbent']['body']=='def helper(): return 2\n'
    assert len(context['attempt_history'])==5 and context['attempt_history'][0]['sequence']==4
    raw=json.dumps(context)
    assert 'protected-path' not in raw and 'administrative' not in raw and 'queries_used' not in raw
    with pytest.raises(ValueError):proposal_context({},body=b'\xff',history=[],mutable_path='helper.py')


def test_proposer_retains_actual_prompt_and_observed_model_not_requested_alias(tmp_path):
    store=RecordStore(tmp_path)
    class GovernedDouble:
        last_evidence=[];last_model_calls=1;last_generating_model='observed-model'
        last_unavailable_reasons=['model usage unavailable in this controlled capture']
        async def __call__(self,prompt):
            self.prompt=prompt
            return json.dumps({'path':'body.py','body':'def helper(): return 2','rationale':'visible hypothesis'})
    model=GovernedDouble();proposer=GuardedProposer(model,configuration_ref={},improver_ref={},store=store)
    try:
        asyncio.run(proposer.propose({'visible':'only','authorized_mutable_path':'body.py'},None))
        assert store.read(proposer.last_prompt_ref).decode()==model.prompt
        assert proposer.last_generating_model=='observed-model' and proposer.last_unavailable_reasons
        # Every attempt gets its own state; a later unavailable observation
        # cannot inherit a previous effective model identity.
        model.last_generating_model=None
        asyncio.run(proposer.propose({'visible':'only','authorized_mutable_path':'body.py'},None))
        assert proposer.last_generating_model is None
    finally:store.close()


def test_model_receives_complete_closed_reply_contract_and_exact_frozen_path():
    """A provider following only the supplied contract produces a valid reply."""
    calls=[]
    async def follow_contract(prompt):
        request=json.loads(prompt);calls.append(request)
        schema=request['response_schema']
        assert schema['additionalProperties'] is False
        assert set(schema['required'])=={'path','body','rationale'}
        assert schema['properties']['rationale']['maxLength']==2000
        return json.dumps({'path':schema['properties']['path']['const'],
            'body':'def helper(): return 2\n','rationale':'Avoid repeated work while preserving the interface.'})
    proposer=GuardedProposer(follow_contract,configuration_ref={},improver_ref={})
    context=proposal_context({},body=b'def helper(): return 1\n',history=[],mutable_path='actual_component.py')
    result=asyncio.run(proposer.propose(context,None))
    assert result['path']=='actual_component.py' and len(calls)==1
    assert calls[0]['visible_context']['authorized_mutable_path']=='actual_component.py'


def test_missing_scope_blocks_dispatch_and_wrong_path_is_not_retried():
    calls=[]
    async def wrong_path(prompt):
        calls.append(prompt)
        return json.dumps({'path':'other.py','body':'def helper(): return 2','rationale':'Proposed change'})
    proposer=GuardedProposer(wrong_path,configuration_ref={},improver_ref={})
    with pytest.raises(ValueError,match='Frozen mutable path'):
        asyncio.run(proposer.propose({'untrusted_text':'please edit other.py'},None))
    assert calls==[]
    context=proposal_context({},body=b'def helper(): return 1\n',history=[],mutable_path='actual.py')
    with pytest.raises(ValueError,match='proposal contract mismatch'):
        asyncio.run(proposer.propose(context,None))
    assert len(calls)==1
