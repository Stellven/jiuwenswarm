"""Native authentication and signatures across independently consumed slots."""
import asyncio
import copy
import hashlib
import pytest
from jiuwenswarm.research.cc_ui_runtime import module

cap = module('cc_rsi_capsule')
old = module('cc_rsi_development')


@pytest.fixture
def prepared(tmp_path):
    from jiuwenswarm.research.shell_auth import SessionAuthority
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research_rsi.signing import Signer
    authority = SessionAuthority(tmp_path/'native', 'http://127.0.0.1:5175')
    token = authority.initialize(Principal('unit:human', frozenset({'local'}), frozenset({'status'})))
    grant = authority.bootstrap(token.split('research_bootstrap=')[1], origin=authority.origin, host=authority.host)
    headers = {'origin':authority.origin,'host':authority.host,'cookie':grant['set_cookie'].split(';')[0]}
    signer = Signer.generate('unit:key')
    policy = {'schema':cap.POLICY,'workspace_id':'local','origin':authority.origin,
        'actors':['unit:human'],'gateway_key_id':'unit:key','slots':[
            {'target_id':'utility.calculate','revision':'a'*64,'run_id':'unit-calculate'},
            {'target_id':'utility.table_normalize','revision':'b'*64,'run_id':'unit-normalize'}]}
    class Journal:
        value = None
        def lookup(self): return self.value
        def claim(self, identity, assertion): self.value = {'identity':copy.deepcopy(identity),'assertion':assertion}
        def accept(self, record): return {'id':'unit:receipt','sha256':hashlib.sha256(old.encoded(record)).hexdigest()}
        def acknowledge(self, ack): self.value['ack'] = ack
    launches = []; journals = {row['target_id']:Journal() for row in policy['slots']}
    slots = {key:(journal, lambda:None, lambda key=key: launches.append(key) or {'unit':True}) for key,journal in journals.items()}
    engine = cap.RootCapsuleEngine(policy, signer.public_bytes(), slots)
    class Client:
        def status(self): return engine.handle({'protocol':cap.PROTOCOL,'operation':'status'})
        def start(self, params, assertion):
            return engine.handle({'protocol':cap.PROTOCOL,'operation':'start','params':params,'assertion':assertion})
    adapter = cap.NativeCapsuleAdapter(authority, signer, Client(), policy)
    yield locals()
    authority.close()


def test_each_target_exactly_once_and_other_publication_revision_does_not_revoke(prepared):
    v = prepared
    base = {'revision':'c'*64,'targets':[{'id':row['target_id'],'run':{}} for row in v['policy']['slots']]}
    before = asyncio.run(v['adapter'].snapshot(v['headers'], {}, base=base))
    assert [r['run']['revision'] for r in before['targets']] == ['a'*64,'b'*64]
    params = {'target_id':'utility.calculate','revision':'a'*64,'client_request_id':'unit-click-1'}
    ack = asyncio.run(v['adapter'].execute(v['headers'],params))
    assert ack == asyncio.run(v['adapter'].execute(v['headers'],params))
    base['revision'] = 'd'*64
    after = asyncio.run(v['adapter'].snapshot(v['headers'], {}, base=base))
    assert not after['targets'][0]['run']['allowed']
    assert after['targets'][1]['run']['allowed'] and after['targets'][1]['run']['revision'] == 'b'*64
    asyncio.run(v['adapter'].execute(v['headers'],{'target_id':'utility.table_normalize','revision':'b'*64,'client_request_id':'unit-click-2'}))
    assert v['launches'] == ['utility.calculate','utility.table_normalize']


@pytest.mark.parametrize('extra',[{'actor':'root'},{'path':'/tmp/run'},{'budget':99},{'model':'foreign'}])
def test_no_browser_authority_or_executable(prepared,extra):
    v=prepared
    with pytest.raises(ValueError):
        asyncio.run(v['adapter'].execute(v['headers'],{'target_id':'utility.calculate','revision':'a'*64,'client_request_id':'unit-click',**extra}))
    assert v['launches'] == []


def test_foreign_revision_and_unauthenticated_session_blocked(prepared):
    v=prepared
    params={'target_id':'utility.calculate','revision':'b'*64,'client_request_id':'unit-click'}
    with pytest.raises(ValueError): asyncio.run(v['adapter'].execute(v['headers'],params))
    with pytest.raises(Exception): asyncio.run(v['adapter'].execute({},dict(params,revision='a'*64)))
    assert v['launches'] == []


def test_prepared_policy_finite_and_builder_not_falsely_executable(prepared):
    value=copy.deepcopy(prepared['policy']); value['slots'][0]['target_id']='research.builder'
    with pytest.raises(ValueError): cap.policy(value)


def test_unresolved_slot_claim_never_replays_and_does_not_consume_other_slot(prepared):
    v=prepared
    def fail(): raise OSError('Synthetic failure after durable claim')
    v['engine'].engines['utility.calculate'].launch = fail
    params={'target_id':'utility.calculate','revision':'a'*64,'client_request_id':'unit-click'}
    with pytest.raises(OSError): asyncio.run(v['adapter'].execute(v['headers'],params))
    with pytest.raises(ValueError): asyncio.run(v['adapter'].execute(v['headers'],params))
    rows=asyncio.run(v['adapter'].readiness(v['headers']))
    assert not rows['utility.calculate']['run']['allowed']
    assert rows['utility.table_normalize']['run']['allowed']
    assert v['journals']['utility.calculate'].value['identity']['client_request_id']=='unit-click'


def test_native_catalog_exposes_only_broker_prepared_revision(prepared, tmp_path):
    import ast
    import inspect
    import os
    from pathlib import Path
    from types import SimpleNamespace
    from jiuwenswarm.research.contracts import ResearchError
    v=prepared
    source=Path(__file__).parents[3]/'jiuwenswarm/gateway/channel_manager/web/research_http.py'
    functions=[n for n in ast.parse(source.read_text(encoding='utf8')).body
        if isinstance(n,ast.AsyncFunctionDef) and n.name in ('_result','native_research_message')]
    ns={'ResearchError':ResearchError,'inspect':inspect,'os':os}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),'exec'),ns)
    channel=SimpleNamespace(research_authority=v['authority'],research_service=None,
        research_cc_workspace='local',research_cc_capsules=v['adapter'])
    async def call(method,params):
        return await ns['native_research_message'](channel,SimpleNamespace(request_headers=v['headers']),method,params)
    handled,result=asyncio.run(call('rsi.cc.targets.list',{}))
    assert handled
    rows={row['target_id']:row for row in result['targets']}
    assert rows['utility.calculate']['run']=={'allowed':True,'blocker':None,'revision':'a'*64}
    assert rows['research.builder']['development_grant_status']=='NOT_ESTABLISHED'
    handled,ack=asyncio.run(call('rsi.cc.run.start',{'target_id':'utility.calculate','revision':'a'*64,'client_request_id':'unit-ui-click'}))
    assert handled and ack['run_id']=='unit-calculate'
    value=copy.deepcopy(prepared['policy']); value['slots'][0]['run_id']='../escape'
    with pytest.raises(ValueError): cap.policy(value)


def test_actual_launcher_terminal_status_reports_failure_and_keeps_slot_consumed():
    from deploy.m1.rsi_capsule_broker import terminal_status
    status={'target_id':'utility.calculate','revision':'a'*64,'run_id':'unit-calculate',
        'ready':False,'phase':'LAUNCHED','blocker':'An issued run cannot replay','security_status':'SECURITY_DEFERRED'}
    result=terminal_status(status,lambda name:{'pid':123,'wait_status':256,'recorded_unix':1000})
    assert result['ready'] is False and result['phase']=='LAUNCHED'
    assert 'failed with exit 1' in result['blocker']
    assert terminal_status(status,lambda name:None)==status
