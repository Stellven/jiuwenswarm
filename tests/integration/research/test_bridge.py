"""Actual Linux Unix transport and custody; provider deliberately stubbed."""
import os
import stat
import asyncio

import pytest

from jiuwenswarm.research.bridge import BridgeError, ModelBridgeClient, ModelBridgeServer
from jiuwenswarm.research.router_client import PlatformIntegrityError
from tests.unit_tests.research.test_bridge import Ledger, Provider, make_bridge


def _live_receipt():
    """External controller consumes public bytes; it never receives app auth."""
    from scripts.research_live_bridge import validate_receipt
    locator=os.environ.get('AI4R_LIVE_CODEX_RECEIPT')
    if not locator:
        pytest.fail('BLOCKED: original owned native host-probe receipt/profile/account/context is unavailable; zero model dispatch')
    return validate_receipt(locator)


class _LiveReadOnlyEvidence:
    def __init__(self, root):
        import sqlite3
        from pathlib import Path
        self.root=Path(root)
        self.db=sqlite3.connect((self.root/'state/research.sqlite3').as_uri()+'?mode=ro',uri=True)
    def read(self, ref):
        import hashlib
        import json
        from jiuwenswarm.research.contracts import validate
        validate('Ref',ref)
        assert self.db.execute('SELECT sha256 FROM artifacts WHERE id=?',(ref['id'],)).fetchone()==(ref['sha256'],)
        path=self.root/'artifacts/sha256'/ref['sha256'][:2]/ref['sha256']
        assert not path.is_symlink()
        raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==ref['sha256']
        return json.loads(raw)
    def records(self, kind):
        return [self.read({'id':identifier,'sha256':digest}) for identifier,digest in self.db.execute(
            'SELECT r.id,a.sha256 FROM records r JOIN artifacts a ON a.id=r.id WHERE r.kind=? ORDER BY r.rowid',(kind,))]


@pytest.mark.parametrize('function',['worker','verifier'])
def test_live_codex_owned_native_ipc_route_start_trace_and_no_retry(function):
    """Independent original-byte recomputation; absence is never a skip.

    The host probe executes inside production as UID10001. This external
    pytest process needs neither production pytest nor a Docker socket/token.
    Passing these two roles does not complete the original V10 chat/account
    population; the returned limitation remains explicit.
    """
    result=_live_receipt()
    assert result['roles'][function] and all(result['roles'][function].values())
    assert result['complete_v10'] is False
    assert result['limitations']==['ordinary_native_chat_and_account_assertions_remain_required']


def test_live_profile_absence_blocks_before_any_native_effect(monkeypatch):
    monkeypatch.delenv('AI4R_LIVE_CODEX_RECEIPT',raising=False)
    with pytest.raises(pytest.fail.Exception,match='BLOCKED.*zero model dispatch'):
        _live_receipt()


def test_live_evidence_reader_verifies_original_bytes_and_is_read_only(tmp_path):
    import sqlite3
    from jiuwenswarm.research.state import SQLiteRunStore
    store=SQLiteRunStore(tmp_path)
    ref=store.append_record('controlled-live-reader',{'id':'reader-fixture','value':'original exact bytes'})
    reader=_LiveReadOnlyEvidence(tmp_path)
    try:
        assert reader.read(ref)=={'id':'reader-fixture','value':'original exact bytes'}
        assert reader.records('controlled-live-reader')==[reader.read(ref)]
        with pytest.raises(sqlite3.OperationalError):reader.db.execute('DELETE FROM records')
        with pytest.raises(AssertionError):reader.read(ref|{'sha256':'0'*64})
    finally:reader.db.close();store.close()


@pytest.mark.asyncio
async def test_real_owned_socket_capability_and_session(tmp_path):
    ledger = Ledger()
    provider = Provider(ledger)
    path = tmp_path / "private" / "model.sock"
    server = await ModelBridgeServer(make_bridge(ledger, provider), path, allowed_peer_uids={os.geteuid()}).start()
    try:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        client = ModelBridgeClient(path, peer_uid=os.geteuid(), capability=server.capability, session_id=server.session_id)
        assert (await client.call({"limits": {"time_s": 2}}, "prompt"))["text"] == "answer"
        for capability, session in (("wrong", server.session_id), (server.capability, "old")):
            wrong = ModelBridgeClient(path, peer_uid=os.geteuid(), capability=capability, session_id=session)
            with pytest.raises(BridgeError, match="DELIVERY_UNKNOWN"):
                await wrong.call({"limits": {"time_s": 2}}, "prompt")
        assert provider.calls == 1
    finally:
        await server.close()
    assert not path.exists()


@pytest.mark.asyncio
async def test_private_rpc_peer_policy_is_narrow_for_each_finite_operation(tmp_path):
    from jiuwenswarm.research.private_rpc import PrivateRPCClient, PrivateRPCServer
    uid=os.geteuid();seen=[];path=tmp_path/'policy'/'authorization.sock'
    server=await PrivateRPCServer(path,protocol='policy:1',session_id='boot',capability='fixture-capability',
        handlers={'model':lambda value:seen.append('model'),'executor':lambda value:seen.append('executor') or {'ok':True}},
        allowed_uids={uid,uid+1},operation_uids={'model':{uid+1},'executor':{uid}}).start()
    client=PrivateRPCClient(path,protocol='policy:1',session_id='boot',capability='fixture-capability',peer_uid=uid)
    try:
        with pytest.raises(BridgeError,match='DELIVERY_UNKNOWN'):await client.call('model',{})
        assert await client.call('executor',{})=={'ok':True}
        assert seen==['executor']
    finally:await server.close()


@pytest.mark.asyncio
async def test_explicit_containment_waits_for_actual_owned_call_cleanup(tmp_path):
    from tests.unit_tests.research.test_bridge import authorized_context
    started,cleaning,release=asyncio.Event(),asyncio.Event(),asyncio.Event()
    class BlockingProvider(Provider):
        async def invoke_governed(self,*args,**kwargs):
            started.set()
            try:await asyncio.Event().wait()
            finally:cleaning.set();await release.wait()
    ledger=Ledger();provider=BlockingProvider(ledger)
    bridge=make_bridge(ledger,provider,lambda _:authorized_context()|{'limits':{'time_s':30,'model_calls':1,'memory_mb':64}})
    async def authorize(value):
        assert value=={'run_id':'run','request_id':'cancel:one'}
        return {'authorized':True,**value,'invocation_ids':['invocation']}
    path=tmp_path/'contain'/'model.sock'
    server=await ModelBridgeServer(bridge,path,allowed_peer_uids={os.geteuid()},authorize_containment=authorize).start()
    client=ModelBridgeClient(path,peer_uid=os.geteuid(),capability=server.capability,session_id=server.session_id)
    call=asyncio.create_task(client.call({},'prompt'))
    await asyncio.wait_for(started.wait(),5)
    # Losing the client alone does not request provider cancellation.
    call.cancel();await asyncio.gather(call,return_exceptions=True)
    assert not cleaning.is_set()
    contain=asyncio.create_task(client.contain_run('run','cancel:one'))
    await asyncio.wait_for(cleaning.wait(),5)
    assert not contain.done()
    release.set()
    assert await contain=={'contained':True,'run_id':'run','request_id':'cancel:one'}
    assert any(k=='model-call' and value['outcome']=='outcome_unknown' for k,value in ledger.records)
    await server.close()


@pytest.mark.asyncio
async def test_peer_and_socket_mode_refused_before_provider(tmp_path):
    ledger = Ledger()
    provider = Provider(ledger)
    path = tmp_path / "private" / "model.sock"
    server = await ModelBridgeServer(make_bridge(ledger, provider), path, allowed_peer_uids={os.geteuid() + 1}).start()
    try:
        client = ModelBridgeClient(path, peer_uid=os.geteuid(), capability=server.capability, session_id=server.session_id)
        with pytest.raises(BridgeError):
            await client.call({"limits": {"time_s": 2}}, "prompt")
        path.chmod(0o666)
        with pytest.raises(PlatformIntegrityError):
            await client.call({"limits": {"time_s": 2}}, "prompt")
        assert provider.calls == 0
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_finite_private_authorization_rpc_rejects_unknown_operation_and_capability(tmp_path):
    from jiuwenswarm.research.private_rpc import PrivateRPCClient, PrivateRPCServer
    seen = []
    def authorize(payload):
        seen.append(payload)
        return {'authorized': True}
    path = tmp_path / 'authorization' / 'control.sock'
    server = await PrivateRPCServer(path, protocol='test-private:1', session_id='boot', capability='private-boot-token',
        handlers={'authorize': authorize}, allowed_uids={os.geteuid()}).start()
    client = PrivateRPCClient(path, protocol='test-private:1', session_id='boot', capability='private-boot-token', peer_uid=os.geteuid())
    try:
        assert await client.call('authorize', {'execution_id': 'known'}) == {'authorized': True}
        for operation, capability in [('load_module', 'private-boot-token'), ('authorize', 'wrong')]:
            wrong = PrivateRPCClient(path, protocol='test-private:1', session_id='boot', capability=capability, peer_uid=os.geteuid())
            with pytest.raises(BridgeError, match='DELIVERY_UNKNOWN'):
                await wrong.call(operation, {'execution_id': 'foreign'})
        assert seen == [{'execution_id': 'known'}]
    finally:
        await server.close()
    assert not path.exists()
