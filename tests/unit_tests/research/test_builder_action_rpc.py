"""Durable native Builder action authority; no fixture process is a live build."""
import asyncio
import os
import time
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.bridge import BridgeError
from jiuwenswarm.research.executor import ExecutorBlocked, InvocationBinding
from jiuwenswarm.research.executor_rpc import ClaimLedger, ExecutionOperations, RemoteInvocation

pytestmark=pytest.mark.skipif(os.name!='posix',reason='Linux durable broker custody required')
REF={'id':'contract','sha256':'a'*64}


@pytest.mark.asyncio
async def test_action_rpc_reauthorizes_and_refuses_changed_replay(tmp_path):
    active=True
    effects=[]
    contract={'run_id':'run:action','subnode_limits':{'time_s':600}}
    async def authorize(request):
        if not active:raise ExecutorBlocked('CANCELLED')
        return dict(request,contract=contract,execution_deadline_monotonic_s=time.monotonic()+600)
    class Service:
        async def action(self,actual,inputs,*,binding,**selection):
            assert actual==binding.contract==contract
            effects.append(selection)
            return {'ok':True,'files':['poc_patch.py']}
    backend=SimpleNamespace(builder_agent_service=Service(),
        bind_invocation=lambda **kwargs:SimpleNamespace(_binding=InvocationBinding(**kwargs)))
    ledger=ClaimLedger(tmp_path/'ledger')
    operations=ExecutionOperations(backend=backend,authorize=authorize,resolve_inputs=lambda _: {},ledger=ledger)
    class RPC:
        async def call(self,operation,payload,**kwargs):
            assert operation=='builder_action' and 'command' not in payload
            return await operations.handlers()[operation](payload)
    client=RemoteInvocation(RPC(),REF,'inv',contract,'exec')
    args=dict(action='list_files',arguments={},ordinal=1,model_ordinal=1)
    result=await client.builder_action(contract,**args)
    assert await client.builder_action(contract,**args)==result and len(effects)==1
    with pytest.raises(ExecutorBlocked,match='REPLAY_CHANGED'):
        await client.builder_action(contract,**dict(args,action='read_file',arguments={'path':'poc_patch.py'}))
    active=False
    with pytest.raises(ExecutorBlocked,match='CANCELLED'):
        await client.builder_action(contract,**dict(args,ordinal=2,model_ordinal=2))
    assert len(effects)==1
    ledger.close()


@pytest.mark.asyncio
async def test_uncertain_action_is_never_reexecuted(tmp_path):
    effects=[]
    contract={'run_id':'run:action'}
    async def authorize(request):
        return dict(request,contract=contract,execution_deadline_monotonic_s=time.monotonic()+60)
    class Service:
        async def action(self,*args,**kwargs):
            effects.append(True)
            raise asyncio.CancelledError()
    backend=SimpleNamespace(builder_agent_service=Service(),
        bind_invocation=lambda **kwargs:SimpleNamespace(_binding=InvocationBinding(**kwargs)))
    ledger=ClaimLedger(tmp_path/'ledger')
    operations=ExecutionOperations(backend=backend,authorize=authorize,resolve_inputs=lambda _: {},ledger=ledger)
    payload={'contract_ref':REF,'invocation_id':'inv','execution_id':'exec','action':'list_files',
             'arguments':{},'ordinal':1,'model_ordinal':1}
    with pytest.raises(asyncio.CancelledError):await operations.builder_action(payload)
    with pytest.raises(BridgeError,match='DELIVERY_UNKNOWN'):await operations.builder_action(payload)
    assert effects==[True] and not operations.active_tasks
    ledger.close()
