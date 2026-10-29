"""Independent IF016 claim/deadline/capture controls, no live qualification."""
import copy
import json
import time

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_evaluation_authority import source_fixture,capture_runtime,product_state


@pytest.mark.asyncio
async def test_private_capture_only_sink_reconstructs_exact_original_claim(tmp_path):
    from jiuwenswarm.research.evaluation_authority import capture_evaluation_native
    store,provider,actor,request,prompts=await source_fixture(tmp_path)
    try:
        authority=provider.resources.bind_runtime(capture_runtime(store,provider,[request]))
        before=product_state(store);req=authority.accept_request(actor,request,'E3');scope=authority.prepare(req)
        grant_ref=authority.prepare_assignment(scope,'worker',None);grant=store.read_record(grant_ref)
        contract=store.read_record(grant['contract_ref']);context=authority.start_assignment(grant_ref,authority.runner._decode_inputs(contract))
        await authority.runner._await_start(context)
        protected=authority.runner.authorize_model_context({'execution_id':grant['execution_id'],'call_ordinal':1})
        context={k:protected[k] for k in ('execution_id','invocation_id','call_id','call_claim_ref','contract_ref')}
        record={'id':'controlled-input','run_id':contract['run_id'],'invocation_id':grant['invocation_id'],
            'call_id':protected['call_id'],'prompt':'controlled original input bytes'}
        ref=capture_evaluation_native(store,'model-call-input',record,context=context)
        assert store.read_record(ref)==record
        assert authority.captures(req,'prompt')[-1]['capture_ref']==ref
        for key,value in [('execution_id','foreign'),('contract_ref',scope),('call_claim_ref',grant_ref),('call_id','foreign')]:
            with pytest.raises(ResearchError):capture_evaluation_native(store,'model-call-input',dict(record,id='forged-'+key),context=context|{key:value})
        live=authority.authorize_model_dispatch(context)
        assert live['call_id']==protected['call_id'] and live['limits']['time_s']<=protected['limits']['time_s']
        with pytest.raises(ResearchError):authority.authorize_model_context({'execution_id':grant['execution_id'],'call_ordinal':1})
        assert len(authority.captures(req,'model_claim'))==1 and prompts==[] and product_state(store)==before
    finally:store.close()


@pytest.mark.asyncio
async def test_original_deadline_and_consumed_slot_survive_reopen(tmp_path):
    from jiuwenswarm.research.evaluation_authority import EvaluationAuthority
    store,provider,actor,request,prompts=await source_fixture(tmp_path)
    try:
        authority=provider.resources.bind_runtime(capture_runtime(store,provider,[request],seconds=.001))
        req=authority.accept_request(actor,request,'E3');original=store.read_record(req)
        with pytest.raises(ResearchError,match='deadline'):authority.prepare(req)
        assert authority.accept_request(actor,request,'E3')==req
        assert store.read_record(req)['started_unix_ns']==original['started_unix_ns']
        assert store.read_record(req)['deadline_unix_ns']==original['deadline_unix_ns']
        # Reconstructing the installed owner may read history; it cannot resume
        # the already-consumed original request or reset its first deadline.
        authority.runner._evaluation_owners.remove(authority)
        reopened=EvaluationAuthority(provider.resources,authority.runtime_ref)
        assert reopened.accept_request(actor,request,'E3')==req
        with pytest.raises(ResearchError,match='inspection'):reopened.prepare(req)
        with pytest.raises(ResearchError):reopened.accept_request(actor,request|{'request_id':'changed'},'E3')
        assert prompts==[]
    finally:store.close()


@pytest.mark.asyncio
async def test_duplicate_original_json_is_rejected_before_slot_claim(tmp_path):
    store,provider,actor,request,prompts=await source_fixture(tmp_path)
    try:
        authority=provider.resources.bind_runtime(capture_runtime(store,provider,[request]))
        body=b'{"request_id":"duplicate",'+json_bytes(request)[1:]
        with pytest.raises(ResearchError):authority.accept_request(actor,request,'E3',original_body=body)
        assert store.connection.execute('SELECT COUNT(*) FROM evaluation_requests').fetchone()[0]==0
        assert not authority.runner._executions and prompts==[]
    finally:store.close()
