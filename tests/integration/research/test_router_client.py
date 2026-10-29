"""Real child/socket routing with controlled replies; no live provider claim."""
import asyncio
import json
import os
import sys
import time

import pytest

from jiuwenswarm.research.router_client import RouterPort, PlatformIntegrityError
from tests.unit_tests.research.test_router_client import context

CHILD = r'''
import json,os,socket,struct,sys,time
path,mode=sys.argv[1:]
with socket.socket(socket.AF_UNIX) as server:
    server.bind(path);os.chmod(path,0o660);server.listen(1)
    print('ready',flush=True)
    connection,_=server.accept()
    with connection:
        size=struct.unpack('!I',connection.recv(4))[0]
        body=b''
        while len(body)<size:body+=connection.recv(size-len(body))
        request=json.loads(body)
        assert request['protocol']=='ai4r-router-ipc:1' and request['op']=='route'
        if mode=='hang':time.sleep(60)
        elif mode=='reset':pass
        else:
            value={'protocol':'ai4r-router-ipc:1','kind':'integrity_fault'} if mode=='integrity' else {'protocol':'foreign','kind':'decision'}
            data=json.dumps(value).encode();connection.sendall(struct.pack('!I',len(data))+data)
'''


async def child(path, mode):
    process=await asyncio.create_subprocess_exec(sys.executable,'-I','-c',CHILD,str(path),mode,
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    assert await asyncio.wait_for(process.stdout.readline(),5)==b'ready\n'
    return process


async def stop(process):
    if process.returncode is None:process.terminate()
    await asyncio.wait_for(process.wait(),5)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,expected',[('reset','error'),('malformed','invalid_decision')])
async def test_actual_child_transport_failure_has_exact_prestart_fallback(tmp_path, mode, expected):
    path=tmp_path/'router.sock';process=await child(path,mode)
    try:
        result=await RouterPort(path,peer_uid=os.geteuid()).select(context(True))
        assert result.model_id=='codex-cli-default' and result.router_failure==expected
        assert result.decision_source=='codex_router_failed' and result.route_decision_ref is None
    finally:await stop(process)


@pytest.mark.asyncio
async def test_actual_missing_and_killed_router_never_prevent_fixed_fallback(tmp_path):
    path=tmp_path/'router.sock';port=RouterPort(path,peer_uid=os.geteuid())
    assert (await port.select(context(True))).router_failure=='missing'
    process=await child(path,'hang');await stop(process)
    assert (await port.select(context(True))).router_failure=='error'
    assert (await port.select(context(False))).decision_source=='codex_router_disabled'
    assert (await port.select(context(True,'verifier'))).decision_source=='codex_router_disabled'


@pytest.mark.asyncio
async def test_actual_hung_process_is_independently_bounded_at_30_seconds(tmp_path):
    path=tmp_path/'router.sock';process=await child(path,'hang');start=time.monotonic()
    try:
        result=await RouterPort(path,peer_uid=os.geteuid()).select(context(True))
        assert result.router_failure=='timeout' and result.model_id=='codex-cli-default'
        assert 29.5<=time.monotonic()-start<35
    finally:await stop(process)


@pytest.mark.asyncio
async def test_actual_platform_integrity_reply_never_becomes_fallback(tmp_path):
    path=tmp_path/'router.sock';process=await child(path,'integrity')
    try:
        with pytest.raises(PlatformIntegrityError):
            await RouterPort(path,peer_uid=os.geteuid()).select(context(True))
    finally:await stop(process)


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['socket_mode','peer_uid'])
async def test_actual_bad_router_custody_is_not_contacted(tmp_path,fault):
    path=tmp_path/'router.sock';process=await child(path,'hang')
    try:
        if fault=='socket_mode':path.chmod(0o600)
        port=RouterPort(path,peer_uid=os.geteuid()+1 if fault=='peer_uid' else os.geteuid())
        result=await port.select(context(True))
        assert result.router_failure=='error' and result.model_id=='codex-cli-default'
        assert process.returncode is None
    finally:await stop(process)


@pytest.mark.asyncio
async def test_poststart_provider_failure_retains_one_call_after_actual_router_loss(tmp_path):
    from jiuwenswarm.research.bridge import GovernedBridge,BridgeError
    from tests.unit_tests.research.test_bridge import Ledger,Provider,authorized_context
    ledger=Ledger();provider=Provider(ledger);provider.fail=True
    protected=authorized_context();protected['router']=context(True)['router'];protected['route_request']={'execution_id':'execution'}
    protected['approved_model_ids']=[]
    bridge=GovernedBridge(persist=ledger.append,authorize=lambda _:protected,revalidate=lambda _:protected,
        subscription_service=provider,router_port=RouterPort(tmp_path/'missing.sock',peer_uid=os.geteuid()))
    with pytest.raises(BridgeError):await bridge.call({},'Controlled component failure')
    assert provider.calls==1
    route=next(v for k,v in ledger.records if k=='route-record')
    outcome=next(v for k,v in ledger.records if k=='model-call')
    assert route['model_id']=='codex-cli-default' and route['router_failure']=='missing'
    assert outcome['outcome']=='outcome_unknown'
