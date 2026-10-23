"""Linux durable Builder-test dispatch; no generated process is launched."""
import json
import os
import time
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.bridge import BridgeError
from jiuwenswarm.research.executor import ExecutorBlocked, InvocationBinding
from jiuwenswarm.research.executor_rpc import ClaimLedger, ExecutionOperations, RemoteInvocation

pytestmark = pytest.mark.skipif(os.name != 'posix', reason='Linux broker custody primitives required')
REF = {'id':'unit-contract','sha256':'a'*64}
OTHER = {'id':'unit-other','sha256':'b'*64}


@pytest.mark.asyncio
async def test_builder_test_rpc_reauthorizes_replays_receipt_and_rejects_substitution(tmp_path):
    active, effects, reports = True, [], {}
    contract={'run_id':'run:rpc','subnode_limits':{'time_s':60}}
    async def authorize(request):
        if not active: raise ExecutorBlocked('CANCELLED')
        return dict(request,contract=contract,execution_deadline_monotonic_s=time.monotonic()+60)
    async def resolve(actual):
        assert actual==contract
        return {'frozen':'inputs'}
    class Service:
        async def test(self, actual, inputs, *, binding, manifest_ref, tests_ref, ordinal):
            assert actual==binding.contract==contract and inputs=={'frozen':'inputs'}
            effects.append(ordinal)
            reports['report']=json.dumps(dict(manifest_ref=manifest_ref,tests_ref=tests_ref,ordinal=ordinal)).encode()
            return {'report_ref':{'id':'report','sha256':'c'*64}}
    backend=SimpleNamespace(builder_test_service=Service(),read_blob=lambda ref:reports[ref['id']],
        bind_invocation=lambda **kwargs: SimpleNamespace(_binding=InvocationBinding(**kwargs)))
    ledger=ClaimLedger(tmp_path/'ledger')
    operations=ExecutionOperations(backend=backend,authorize=authorize,resolve_inputs=resolve,ledger=ledger)
    class RPC:
        async def call(self,operation,payload,**kwargs):
            assert operation=='builder_test' and 'command' not in payload
            return await operations.builder_test(payload)
    client=RemoteInvocation(RPC(),REF,'inv:rpc',contract,'exec:rpc')
    first=await client.builder_test(contract,manifest_ref=REF,tests_ref=OTHER,ordinal=1)
    assert await client.builder_test(contract,manifest_ref=REF,tests_ref=OTHER,ordinal=1)==first
    assert effects==[1]
    with pytest.raises(ExecutorBlocked,match='REPLAY_CHANGED'):
        await client.builder_test(contract,manifest_ref=OTHER,tests_ref=OTHER,ordinal=1)
    active=False
    with pytest.raises(ExecutorBlocked,match='CANCELLED'):
        await client.builder_test(contract,manifest_ref=REF,tests_ref=OTHER,ordinal=2)
    assert effects==[1]
    ledger.close()


@pytest.mark.asyncio
async def test_uncertain_builder_test_is_not_reexecuted(tmp_path):
    effects=[]
    contract={'run_id':'run:rpc'}
    async def authorize(request):
        return dict(request,contract=contract,execution_deadline_monotonic_s=time.monotonic()+60)
    class Service:
        async def test(self,*args,**kwargs):
            effects.append('started')
            raise RuntimeError('lost receipt')
    backend=SimpleNamespace(builder_test_service=Service(),bind_invocation=lambda **kwargs:SimpleNamespace(_binding=InvocationBinding(**kwargs)))
    ledger=ClaimLedger(tmp_path/'ledger')
    operations=ExecutionOperations(backend=backend,authorize=authorize,resolve_inputs=lambda contract:{},ledger=ledger)
    payload={'contract_ref':REF,'invocation_id':'inv:rpc','execution_id':'exec:rpc','manifest_ref':REF,'tests_ref':OTHER,'ordinal':1}
    with pytest.raises(RuntimeError,match='lost receipt'): await operations.builder_test(payload)
    with pytest.raises(BridgeError,match='DELIVERY_UNKNOWN'): await operations.builder_test(payload)
    assert effects==['started']
    ledger.close()
