"""Controlled health vectors only; no model, fixture execution or READY claim."""
import asyncio
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.runtime_readiness import (
 RuntimeReadiness,CustodianRuntimeReadiness,RUNTIME_CHECKS,HEARTBEAT_CHECKS,
 native_observation,readonly_history,validate_report,_report)


def _pin(name='controlled'):return {'id':name,'sha256':hashlib.sha256(name.encode()).hexdigest()}


def test_native_inspection_uses_existing_process_and_original_account_observation_only(tmp_path,monkeypatch):
 from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
 class Transport:
  listeners=set();process=SimpleNamespace(pid=os.getpid(),returncode=None)
  _reader=SimpleNamespace(done=lambda:False)
  async def start(self):pytest.fail('Doctor started model backend')
  async def request(self,*_):pytest.fail('Doctor contacted provider/account backend')
 core=SQLiteRunStore(tmp_path/'core')
 try:
  service=SubscriptionService(tmp_path/'account',transport=Transport())
  service._observation_identity_verified=True;service.account_fingerprint='controlled-synthetic-fingerprint'
  service.account_observation_state={'status':'observed','reason':None}
  observation={'schema':'ai4r-subscription-account-observation:1','id':'controlled-observation',
   'observed_at':datetime.now(timezone.utc).isoformat(),'status':'observed','sparse_update':False,
   'epoch':service.epoch,'account_fingerprint':service.account_fingerprint,
   'profile_id':hashlib.sha256(str(service.root).encode()).hexdigest()}
  service.last_account_observation=observation
  pin=core.append_record('subscription-account-observation',observation)
  resources=SimpleNamespace(store=core,bridge=SimpleNamespace(subscription=service,_active_calls={},_uncertain_runs=set()))
  lease=SimpleNamespace(assert_available=lambda:None)
  before=core.connection.total_changes
  assert native_observation(resources,lease)==[pin]
  assert core.connection.total_changes==before
  observation['observed_at']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
  with pytest.raises(ValueError):native_observation(resources,lease)
  assert not service.root.exists()
 finally:core.close()


def test_missing_or_running_native_effect_cannot_be_repaired_by_health(tmp_path):
 from jiuwenswarm.research_rsi.native_lease import ProfileInUse
 def unavailable():raise ProfileInUse('controlled unknown effect')
 with pytest.raises(ProfileInUse):native_observation(None,SimpleNamespace(assert_available=unavailable))
 service=SimpleNamespace(transport=SimpleNamespace(process=None))
 with pytest.raises(ValueError):native_observation(SimpleNamespace(bridge=SimpleNamespace(subscription=service)),SimpleNamespace(assert_available=lambda:None))


def test_history_checks_execute_selects_without_clearance_migration_or_phase_mutation(tmp_path,monkeypatch):
 store=RecordStore(tmp_path/'records');session=store.put({'session_id':'fresh'})
 def forbidden(*_):pytest.fail('Readiness attempted a durable history/clearance mutation')
 try:
  for name in ('security_halts','record_clearances','record_security_halt','advance_phase','put'):
   monkeypatch.setattr(store,name,forbidden)
  before=store.db.total_changes
  assert readonly_history(store,session)==[]
  assert store.db.total_changes==before
 finally:store.close()


def test_unresolved_historical_or_already_claimed_session_blocks_without_recovery(tmp_path):
 store=RecordStore(tmp_path/'records');session=store.put({'session_id':'fresh'});unit=store.put({'controlled':'history'})
 try:
  store.db.execute('INSERT INTO session_history VALUES(?,?,?,NULL,NULL,NULL,1)',('old',json.dumps(unit),json.dumps(unit)))
  before=store.db.total_changes
  with pytest.raises(ValueError):readonly_history(store,session)
  assert store.db.total_changes==before
  store.db.execute('DELETE FROM session_history')
  job=_pin('job_controlled');store.claim_job(job)
  before=store.db.total_changes
  with pytest.raises(ValueError):readonly_history(store,session,job_ref=job)
  assert store.db.total_changes==before
 finally:store.close()


def test_clearance_is_independently_validated_without_recording_acknowledgement(tmp_path):
 store=RecordStore(tmp_path/'records');unit=store.put({'controlled':'original nonsecret'})
 prior=store.put({'session_id':'halted'});fresh=store.put({'session_id':'new'})
 try:
  incident=store.record_security_halt('halted',prior,'operator','controlled source violation')
  clearance=store.put({'schema_version':'1.0.0','id':'controlled:clearance','halted_session_id':'halted',
   'actor_id':'independent-reviewer','recorded_at':'2030-01-01T00:00:00Z','decision':'cleared',
   'effect_scope':'new_rsi_session_only','violation_refs':[incident],'remediation_ref':unit,'guardrail_evidence_refs':[unit]})
  policy=store.put({'schema':'ai4r-rsi-clearance-policy:1','id':'controlled:policy','authorized_reviewers':['independent-reviewer'],'clearance_refs':[clearance]})
  before=store.db.total_changes
  assert readonly_history(store,fresh,clearance_policy_ref=policy)==[policy,clearance]
  assert store.db.total_changes==before
  assert store.db.execute('SELECT clearance_ref FROM security_halts').fetchone()[0] is None
  with pytest.raises(ValueError):readonly_history(store,prior,clearance_policy_ref=policy)
 finally:store.close()


def test_custodian_health_client_sends_existing_ref_without_creating_request_blob(monkeypatch):
 from jiuwenswarm.research_rsi import custodian_client
 calls=[];session=_pin('session')
 async def request(path,uid,operation,pin,**kwargs):
  calls.append((operation,pin));return {'status':'ok','result':{'controlled':'response'}}
 monkeypatch.setattr(custodian_client,'request',request)
 class Requests:
  def put(self,*_):pytest.fail('Health created a custody request artifact')
 client=custodian_client.CustodianClient(Requests(),socket_path='/controlled/socket',peer_uid=12002,session_id='controlled')
 assert asyncio.run(client.readiness(session))=={'controlled':'response'}
 assert calls==[('custodian_readiness',session)]


def _ready(schema='ai4r-rsi-runtime-readiness:1'):
 checks=RUNTIME_CHECKS if schema=='ai4r-rsi-runtime-readiness:1' else HEARTBEAT_CHECKS
 return _report(schema,_pin('session'),_pin('target'),_pin('worker'),
  [{'check':code,'state':'READY','proof_refs':[]} for code in checks])


def test_forged_serialized_ready_cannot_hide_blocked_or_omitted_findings():
 report=_ready();validate_report(report)
 report['findings'][0]['state']='BLOCKED'
 with pytest.raises(ValueError):validate_report(report)
 report=_ready();report['findings'][-1]=report['findings'][0]
 with pytest.raises(ValueError):validate_report(report)


def test_job_health_calls_only_installed_readonly_hook_not_factory_start_or_job_claim():
 from jiuwenswarm.research_rsi.ports import JobPort
 report=_ready();ref=_pin('job_controlled');seen=[]
 class Factory:
  def __call__(self,*_):pytest.fail('Health assembled writable execution factory')
  async def readiness(self,job,*,job_ref=None):seen.append(job_ref);return report
 class Jobs:
  factory=Factory()
  def resolve(self,*_):return {'session_ref':report['session_ref']}
 class Store:
  def read(self,*_):pytest.fail('Health read an unrelated artifact')
  def __getattr__(self,name):pytest.fail('Health touched mutable job operation '+name)
 port=JobPort(Jobs(),Store(),allowed_refs=[ref])
 assert asyncio.run(port.readiness(ref))==report and seen==[ref]


def test_live_doctor_uses_current_service_not_static_wal_snapshot(tmp_path,monkeypatch):
 from jiuwenswarm.research_rsi import readiness,ports
 pin=_pin('job_controlled');report=_ready();calls=[]
 monkeypatch.setattr(readiness,'_regular',lambda *a,**k:b'{}')
 monkeypatch.setattr(readiness,'_path',lambda v:Path(v))
 monkeypatch.setattr(readiness,'load_config',lambda *a:{'allowed_job_refs':[pin],'socket_path':'/controlled/jobs.sock'})
 def forbidden(*_):pytest.fail('Live doctor used stale immutable SQLite or static diagnostic')
 monkeypatch.setattr(readiness,'check_doctor',forbidden)
 monkeypatch.setattr(readiness._ReadOnlyCaptures,'__init__',forbidden)
 async def request(path,uid,operation,ref,**kwargs):
  calls.append((uid,operation,ref));return {'status':'ok','result':report}
 monkeypatch.setattr(ports,'request',request)
 value=asyncio.run(readiness.check_doctor_live('/controlled/config.json'))
 assert value['status']=='READY' and value['eligible_for']=='human_session_start'
 assert calls==[(12001,'session_readiness',pin)]
 assert value['ready_job_refs']==[pin]


def test_live_doctor_missing_config_stays_blocked_and_exposes_no_path(tmp_path):
 from jiuwenswarm.research_rsi.readiness import check_doctor_live
 path=tmp_path/'sensitive-account-path'/'missing.json'
 result=asyncio.run(check_doctor_live(path))
 assert result['status']=='BLOCKED' and result['blockers']==['SERVICE_CONFIG']
 assert 'sensitive-account-path' not in json.dumps(result) and not path.parent.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize('calls',[1,2])
async def test_bounded_diagnosis_contract_reads_real_authority_and_reservations_without_claiming(tmp_path,calls):
 from tests.unit_tests.research.test_budget_ceiling import work_contract
 from jiuwenswarm.research_rsi.runtime_readiness import diagnosis_contract
 from jiuwenswarm.research_rsi.profiles import Limits
 from dataclasses import asdict
 core,runner,pin,contract=await work_contract(tmp_path,calls=calls)
 frozen=runner._run_contexts[contract['run_id']]
 resources=SimpleNamespace(store=core,runner=runner,principal=SimpleNamespace(account_id='alice'),
  exact_binding_refs={'model_selection_profile_ref':frozen['model_selection_profile_ref'],'deployment_ref':frozen['deployment_ref']})
 session={'configuration_ref':contract['configuration_ref'],'limits':asdict(Limits())}
 job={'diagnosis_contract_ref':pin,'proposer_contract_refs':[_pin('other-contract')]}
 try:
  before=core.connection.total_changes;node_started=dict(runner._node_started)
  if calls==1:
   with pytest.raises(ValueError):diagnosis_contract(resources,session,job)
  else:
   assert diagnosis_contract(resources,session,job)==[pin,contract['node_contract_ref']]
  assert core.connection.total_changes==before and runner._node_started==node_started
  assert not list(core.iter_records(kinds=('model-call-start','node-budget-start','invocation-preparation')))
  if calls==2:
   assert core.claim_attempt(pin,contract)
   with pytest.raises(ValueError):diagnosis_contract(resources,session,job)
 finally:core.close()


def test_custodian_heartbeat_observes_frozen_owners_without_opening_ledger_or_running_fixture(tmp_path,monkeypatch):
 """The calibration verifier below is an explicit unit-only owner double."""
 from jiuwenswarm.research_rsi.custody import ExposureLedger
 from tests.unit_tests.research_rsi.test_session_policy import budget_record
 import jiuwenswarm.research_rsi.targets.ranking_preparation as calibration_module
 records=RecordStore(tmp_path/'records');ledger=ExposureLedger(tmp_path/'ledger.sqlite')
 calibration=records.put({'schema':'ai4r-rsi-calibration:2','controlled':'unit verifier double, not actual calibration'})
 target={'calibration_ref':calibration};target_ref=records.put(target)
 plan=budget_record(target_ref);genesis=records.put({'final_budget_ref':records.put(plan)})
 session={'session_id':'controlled-session','target_profile_ref':target_ref,'chain_root_ref':genesis,
  'pass_count_repeats':1,'limits':{'wall_s':30}}
 session_ref=records.put(session)
 unit=records.put({'controlled':'immutable runtime context'})
 profile=records.put({'schema':'ai4r-rsi-worker-profile:3','target_kind':'ranking-v1','process_policy':'single_process_seccomp_v1',
  'session_ref':session_ref,'target_ref':target_ref,'parent_ref':unit,'contract_ref':unit,
  'environment_ref':unit,'hardware_ref':unit,'memory_mb':128,'pids_max':16,'timeout_s':.005})
 partitions={name:[{'id':name+str(index)} for index in range(20)] for name in ('development','hidden_loop','hidden_final','platform')}
 manifest={'target_ref':target_ref,'calibration_ref':calibration,'fixture_identity':'controlled-fixtures','partitions':partitions}
 manifest_ref=records.put(manifest)
 ledger.register(manifest['fixture_identity'],{name:[row['id'] for row in rows] for name,rows in partitions.items()},known_bad=10,known_good=3)
 invocations=[]
 async def prerequisites():
  invocations.append('worker-health');return {'ready':True,'limitations':[],'worker_uid':12003,'profile_refs':[profile]}
 def forbidden(*_):pytest.fail('Heartbeat executed a fixture or mandatory check')
 runtime=SimpleNamespace(session_ref=session_ref,target=target,worker=SimpleNamespace(profile_ref=profile,prerequisites=prerequisites),
  mandatory=forbidden,paired=forbidden)
 def verified(*args,**kwargs):
  invocations.append('calibration-read');return {'known_bad_rejected':10,'known_good_qualified':3,'measurable_headroom':True,'worker_profile_ref':profile}
 monkeypatch.setattr(calibration_module,'verify_calibration2',verified)
 inspector=CustodianRuntimeReadiness(records,ledger,{session['session_id']:session},{session['session_id']:runtime},manifest,
  manifest_ref=manifest_ref,public_key=b'x'*32,key_id='controlled')
 import jiuwenswarm.research.contracts.rsi_installation as installation_module
 class ControlledQualification:
  installation=SimpleNamespace(public_key=b'x'*32,key_id='controlled')
  def require(self,*args,**kwargs):return {'qualification_ref':_pin('unit-not-qualification'),'scope_ref':_pin('unit-not-scope')}
 monkeypatch.setattr(installation_module,'installed_consumer_qualification',lambda *_:ControlledQualification())
 try:
  before=(records.db.total_changes,ledger.db.total_changes)
  report=asyncio.run(inspector.inspect(session_ref))
  assert report['status']=='READY' and invocations==['calibration-read','worker-health']
  assert (records.db.total_changes,ledger.db.total_changes)==before
  assert ledger.db.execute('SELECT count(*) FROM sessions').fetchone()[0]==0
  ledger.open_session(session['session_id'],manifest['fixture_identity'])
  before=(records.db.total_changes,ledger.db.total_changes)
  assert 'CUSTODIAN_HISTORY' in asyncio.run(inspector.inspect(session_ref))['blockers']
  assert (records.db.total_changes,ledger.db.total_changes)==before
  monkeypatch.setattr(calibration_module,'verify_calibration2',lambda *a,**k:True)
  assert 'CUSTODIAN_CALIBRATION' in asyncio.run(inspector.inspect(session_ref))['blockers']
  foreign=records.get(profile);foreign['hardware_ref']=records.put({'controlled':'other hardware'})
  foreign_profile=records.put(foreign)
  monkeypatch.setattr(calibration_module,'verify_calibration2',lambda *a,**k:{
   'known_bad_rejected':10,'known_good_qualified':3,'measurable_headroom':True,'worker_profile_ref':foreign_profile})
  assert 'CUSTODIAN_CALIBRATION' in asyncio.run(inspector.inspect(session_ref))['blockers']
 finally:records.close();ledger.close()


def test_custodian_readonly_endpoint_uses_exact_existing_session_grant():
 from jiuwenswarm.research_rsi.custodian_service import CustodianService
 session_ref=_pin('session');session={'session_id':'controlled'};seen=[]
 inspector=object.__new__(CustodianRuntimeReadiness)
 async def inspect(pin):seen.append(pin);return _ready('ai4r-rsi-custodian-readiness:1')
 inspector.inspect=inspect
 class Requests:
  def get(self,*_):pytest.fail('Readiness interpreted a newly supplied custody request')
 service=CustodianService(Requests(),None,None,None,None,None,['controlled'],
  session_grants={'controlled':{'session_ref':session_ref}},public_store=SimpleNamespace(get=lambda _:session),readiness_inspector=inspector)
 assert asyncio.run(service.readiness(session_ref))['status']=='READY' and seen==[session_ref]
 with pytest.raises(PermissionError):asyncio.run(service.readiness(_pin('foreign-session')))


def test_normal_factory_native_refusal_is_not_ignored(monkeypatch):
 from jiuwenswarm.research_rsi import fixed_resources
 from jiuwenswarm.research_rsi.native_lease import ProfileInUse
 async def refused(*_):return False
 monkeypatch.setattr(fixed_resources,'native_profile_ready',refused)
 with pytest.raises(ProfileInUse):asyncio.run(fixed_resources.require_native_profile_ready(None,None))


def test_malformed_installed_qualification_stays_unavailable_without_fallback_effect_authority(monkeypatch):
 from jiuwenswarm.research_rsi.fixed_resources import qualification_or_unavailable
 import jiuwenswarm.research_rsi.qualification as qualification
 def malformed(*args,**kwargs):raise ValueError('controlled malformed installation; no path exposure')
 monkeypatch.setattr(qualification,'configured_qualification',malformed)
 assert qualification_or_unavailable(None,_pin('qualification')) is None
 with pytest.raises(ValueError):qualification.require_qualification(None,'session_start',session_ref=_pin('session'))
