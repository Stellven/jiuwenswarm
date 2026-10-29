import asyncio

import pytest

from jiuwenswarm.research.control import ResearchService
from jiuwenswarm.research.contracts import Principal,ResearchError
from jiuwenswarm.research.runner import Registry
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.state import json_bytes


@pytest.mark.asyncio
async def test_submit_claims_before_compiler_once_and_normalizes_actor(tmp_path, monkeypatch):
    # This tests durable request allocation, not run-input qualification (which
    # has its own connected tests). The original blob placeholders are not a
    # valid protected resource capture and must never grant product execution.
    monkeypatch.setattr('jiuwenswarm.research.run_inputs.prepare_run_inputs',
        lambda store, run_id, principal, protected: dict(protected))
    store=SQLiteRunStore(tmp_path);ref=store.put_blob(b'protected')
    configuration=store.put_blob(json_bytes({'schema_version':'1.0.0','cc':{'plan_source':'static','plan_policy_ref':ref,'static_template_ref':ref,'evaluation_profile_ref':None,
        'router':{'enabled':False,'deadline_s':30,'profile_ref':None}},'rsi':{'custodian_key_id':None,'custodian_public_key':None},'codex':{'route_id':'codex-cli-default'},'role_aliases':{}}))
    entered=asyncio.Event();release=asyncio.Event();calls=[]
    async def compile_once(run_id,protected):
        assert store.get_run(run_id)['account_id']=='alice'
        calls.append(run_id);entered.set();await release.wait();return {'accepted':False}
    service=ResearchService(store,registry=Registry(),model=None,compiler=compile_once)
    service.configure_workspace('alice','project',configuration_ref=configuration,profile_ref=ref,workspace_ref=ref,input_directory_ref=ref)
    principal=Principal('alice',frozenset({'project'}),frozenset({'submit','status','reconcile','export'}))
    intake=await service.ingest(principal,'Investigate retrieval latency',workspace_id='project')
    request={'schema_version':'1.0.0','id':'submit:one','client_request_id':'request-1','account_id':'forged',
             'workspace_id':'project','configuration_ref':configuration,'intake_ref':intake}
    first=await service.submit(principal,request)
    await asyncio.wait_for(entered.wait(), timeout=2)
    second=await service.submit(principal,request)
    assert first['run_id']==second['run_id'] and len(calls)==1
    with pytest.raises(ResearchError,match='identity_conflict'):
        await service.submit(principal,request|{'interaction_mode':'headless'})
    other=Principal('bob',frozenset({'project'}),frozenset({'status'}))
    with pytest.raises(ResearchError,match='not_found'):await service.get(other,first['run_id'])
    release.set();await asyncio.gather(*service._tasks.values())


@pytest.mark.asyncio
async def test_retrieval_does_not_widen_delivery_audience(tmp_path):
    store=SQLiteRunStore(tmp_path);store.create_run('run:export',account_id='alice',workspace_id='project',submission={})
    secret=store.put_blob(b'for authorized reviewers only');ordinary=store.put_blob(b'public to the requesting researcher')
    manifest={'schema_version':'2.0.0','id':'delivery_manifest','brief_ref':ordinary,'verdict_ref':ordinary,'report_ref':secret,
              'gate_decision_refs':[ordinary],'artifact_refs':[ordinary]*7,'missing_evidence':[],
              'files':[{'path':'review.txt','artifact_ref':secret,'media_type':'text/plain','audience':'reviewer','role':'report'},
                       {'path':'requester.txt','artifact_ref':ordinary,'media_type':'text/plain','audience':'researcher','role':'report'}]}
    manifest['files'].extend({'path':f'evidence_{i}.json','artifact_ref':ordinary,'media_type':'application/json','audience':'researcher','role':'raw_evidence'} for i in range(10))
    manifest_ref=store.put_blob(json_bytes(manifest))
    store.append_record('invocation-observation',{'id':'observation:export','run_id':'run:export','output_refs':[secret,ordinary,manifest_ref]})
    candidate=store.put_blob(b'{"candidate":"exact captured JSON"}')
    store.append_record('captured-output',{'id':'capture:candidate','run_id':'run:export','artifact_ref':candidate,'media_type':'application/json'})
    store.append_record('invocation-observation',{'id':'observation:candidate','run_id':'run:export','output_refs':[candidate]})
    # Test-only accepted-row setup exercises retrieval, not gate acceptance.
    with store.transaction() as db:
        db.execute('INSERT INTO acceptance VALUES(?,?,?,?,?,?,?)',('run:export','delivery','delivery-a1','','manifest',json_bytes(manifest_ref).decode(),'fixture:commit'))
        db.execute('INSERT INTO nodes VALUES(?,?,?,?,?)',('run:export','delivery','completed','delivery-a1',None))
    service=ResearchService(store,registry=Registry(),model=None)
    actor=Principal('alice',frozenset({'project'}),frozenset({'export'}),frozenset({'researcher','reviewer'}))
    researcher,contents=await service.artifact_bytes(actor,'run:export',audience='researcher')
    assert b'for authorized reviewers only' not in contents.values()
    assert 'requester.txt' in contents and 'review.txt' not in contents
    assert researcher['redactions']
    assert next(f for f in researcher['files'] if f['artifact_ref']==candidate)['media_type']=='application/json'
    reviewer,contents=await service.artifact_bytes(actor,'run:export',audience='reviewer')
    assert contents['review.txt']==b'for authorized reviewers only'
    assert all(f['audience']=='reviewer' for f in reviewer['files'])
