"""Read-only checks on already composed owners; no dispatch or reconciliation.

READY describes eligibility for a human to request a fresh bounded session. It
is neither diagnosis START nor a reusable execution/qualification credential.
"""
from __future__ import annotations
import asyncio
from datetime import datetime,timezone
import hashlib
import json
import sqlite3
import time

from jiuwenswarm.research.contracts import ResearchError
from .records import encoded
from .session_policy import validate_private,FinalBudget
from .profiles import Limits,freeze_profile

RUNTIME_CHECKS=('IF015_AUTHORITY','FROZEN_TARGETS','OPPORTUNITY_PREPARATION','WORKER_RUNTIME',
 'CUSTODIAN_RUNTIME','MODEL_RUNTIME','DIAGNOSIS_RUNTIME','SESSION_HISTORY')
HEARTBEAT_CHECKS=('CUSTODIAN_BINDING','CUSTODIAN_CALIBRATION','CUSTODIAN_BUDGET','CUSTODIAN_WORKER','CUSTODIAN_HISTORY')


def _need(value):
 if not value:raise ValueError('Current read-only readiness prerequisite unavailable')


def _proof(pin):
 from .worker import ref
 ref(pin);return pin


def _report(schema,session_ref,target_ref,worker_ref,findings):
 blockers=[row['check'] for row in findings if row['state']!='READY']
 return {'schema':schema,'status':'BLOCKED' if blockers else 'READY','session_ref':session_ref,
  'target_profile_ref':target_ref,'worker_profile_ref':worker_ref,'read_only':True,
  'eligible_for':'human_session_start','findings':findings,'blockers':blockers}


def validate_report(value):
 schema=value.get('schema') if isinstance(value,dict) else None
 _need(schema in {'ai4r-rsi-runtime-readiness:1','ai4r-rsi-custodian-readiness:1'})
 validate_private('urn:ai4r:private:'+('rsi-runtime-readiness:1' if schema=='ai4r-rsi-runtime-readiness:1' else 'rsi-custodian-readiness:1'),value)
 expected=RUNTIME_CHECKS if schema=='ai4r-rsi-runtime-readiness:1' else HEARTBEAT_CHECKS
 _need([row['check'] for row in value['findings']]==list(expected))
 blockers=[row['check'] for row in value['findings'] if row['state']!='READY']
 _need(value['blockers']==blockers and value['status']==('BLOCKED' if blockers else 'READY'))
 return value


async def _check(findings,code,operation):
 try:
  result=operation()
  if hasattr(result,'__await__'):result=await result
  _need(isinstance(result,list));pins=[_proof(pin) for pin in result]
 except (ValueError,KeyError,TypeError,OSError,AttributeError,ImportError,RecursionError,sqlite3.Error,ResearchError):
  findings.append({'check':code,'state':'BLOCKED','proof_refs':[]})
 else:findings.append({'check':code,'state':'READY','proof_refs':pins})


def readonly_history(store,session_ref,*,clearance_policy_ref=None,job_ref=None):
 """Read existing indexes only. Never call mutating clearance/history helpers."""
 session=store.get(session_ref);sid=session['session_id'];db=store.db
 if job_ref is not None:
  _need(db.execute('SELECT 1 FROM jobs WHERE id=?',(job_ref['id'],)).fetchone() is None)
 _need(db.execute('SELECT 1 FROM session_history WHERE session=? OR session_ref=?',(sid,encoded(session_ref).decode())).fetchone() is None)
 _need(db.execute('SELECT 1 FROM history_jobs WHERE session_ref=?',(encoded(session_ref).decode(),)).fetchone() is None)
 # An unresolved original history is not evidence of cessation, even when a
 # later model lease happens to be free. Readiness never repairs this state.
 rows=list(db.execute('SELECT session,session_ref,unsigned_ref,signed_ref,uncertain FROM session_history LIMIT 1025'))
 _need(len(rows)<=1024)
 for prior,prior_session,unsigned,signed,uncertain in rows:
  _need(not uncertain)
  terminal_ref=json.loads(signed or unsigned) if signed or unsigned else None
  terminal=store.get(terminal_ref) if terminal_ref else None
  violations=[]
  for (raw,) in db.execute('SELECT ref FROM attempts WHERE session=?',(prior,)):
   violations.extend(store.get(json.loads(raw)).get('violations',[]))
  if violations or terminal and terminal.get('outcome')=='SECURITY_HALTED':
   _need(db.execute('SELECT 1 FROM security_halts WHERE session=?',(prior,)).fetchone() is not None)
 incidents=list(db.execute('SELECT session,ref,clearance_ref FROM security_halts ORDER BY session LIMIT 1025'))
 _need(len(incidents)<=1024 and all(prior!=sid for prior,_,_ in incidents))
 if not incidents:return []
 _need(clearance_policy_ref is not None)
 policy=store.get(clearance_policy_ref)
 validate_private('urn:ai4r:private:rsi-clearance-policy:1',policy)
 from .clearance import validate_clearance
 from .session_policy import _contracts
 proofs=[clearance_policy_ref]
 for prior,raw_pin,recorded_clearance in incidents:
  pin=json.loads(raw_pin);incident=store.get(pin)
  validate_private('urn:ai4r:private:rsi-security-incident:1',incident)
  _need(incident['session_id']==prior)
  candidates=[(ref,store.get(ref)) for ref in policy['clearance_refs']]
  matches=[(ref,value) for ref,value in candidates if value.get('halted_session_id')==prior]
  _need(len(matches)==1);ref,value=matches[0]
  validate_clearance(value,halted_operator=incident['operator_id'],authorized_reviewers=set(policy['authorized_reviewers']),validate=_contracts().validate)
  _need(pin in value['violation_refs'] and (recorded_clearance is None or json.loads(recorded_clearance)==ref))
  _need(datetime.fromisoformat(value['recorded_at'].replace('Z','+00:00'))>=datetime.fromisoformat(incident['recorded_at'].replace('Z','+00:00')))
  for evidence in [*value['violation_refs'],value['remediation_ref'],*value['guardrail_evidence_refs']]:store.read(evidence)
  proofs.append(ref)
 return proofs


def native_observation(resources,native_lease,*,maximum_age_s=300):
 """Inspect an existing native process and persisted observation, never status()."""
 native_lease.assert_available()
 bridge=resources.bridge;service=bridge.subscription
 from jiuwenswarm.research.fixed_subscription import deployment_backend,HOST_CODEX_BACKEND
 exact=getattr(resources,'exact_binding_refs',None)
 if exact is not None and deployment_backend(resources.store.read_record(exact['deployment_ref']))==HOST_CODEX_BACKEND:
  raise ValueError('Host native readiness requires its asynchronous exact receipt proof')
 transport=service.transport
 process=transport.process
 _need(process is not None and process.returncode is None and type(process.pid) is int and process.pid>0)
 os_module=__import__('os');os_module.kill(process.pid,0)
 _need(transport._reader is not None and not transport._reader.done())
 from jiuwenswarm.research.fixed_subscription import SPARK_REQUESTED_MODEL,deployment_model
 exact=getattr(resources,'exact_binding_refs',None)
 if exact is not None and deployment_model(resources.store.read_record(exact['deployment_ref']))==SPARK_REQUESTED_MODEL:
  from .spark_backend import SparkSubscriptionService
  _need(type(service) is SparkSubscriptionService and not bridge._active_calls and not bridge._uncertain_runs)
  return service.readiness_proof(store=resources.store,deployment_ref=exact['deployment_ref'],maximum_age_s=maximum_age_s)
 _need(not service.active and service.login_id is None and service._observation_identity_verified
    and service.account_fingerprint and not bridge._active_calls and not bridge._uncertain_runs
    and service.account_observation_state.get('status') in {'observed','partial'})
 observation=service.last_account_observation
 _need(isinstance(observation,dict) and observation.get('schema')=='ai4r-subscription-account-observation:1'
    and observation.get('status') in {'observed','partial'} and observation.get('sparse_update') is False
    and observation.get('epoch')==service.epoch and observation.get('account_fingerprint')==service.account_fingerprint
    and observation.get('profile_id')==hashlib.sha256(str(service.root).encode()).hexdigest())
 observed=datetime.fromisoformat(observation['observed_at'].replace('Z','+00:00'))
 age=(datetime.now(timezone.utc)-observed).total_seconds()
 _need(observed.tzinfo is not None and 0<=age<=maximum_age_s)
 matches=[row for row in resources.store.iter_records(kinds=('subscription-account-observation',))
    if row['record']==observation]
 _need(len(matches)==1)
 pin=matches[0]['ref'];_need(resources.store.record_kind(pin)=='subscription-account-observation')
 resources.store.read_blob(pin)
 return [pin]


def diagnosis_contract(resources,session,job):
 """Original contract/checking/read/budget inspection with no start/claim."""
 from jiuwenswarm.research.contracts import validate
 core=resources.store;runner=resources.runner;pin=job['diagnosis_contract_ref']
 contract=core.read_record(pin,contract_id='subnode-execution-contract');validate('subnode-execution-contract',contract)
 _need(core.record_kind(pin)=='subnode-execution-contract' and pin not in job['proposer_contract_refs'])
 runner._require_child_authority(pin,contract);runner._require_check_assets(contract)
 _need(contract['configuration_ref']==session['configuration_ref'] and len(contract['bindings'])==1)
 binding=contract['bindings'][0];authority=binding['effective_authority'];limits=Limits.from_mapping(session['limits'])
 _need(binding['limits']['model_calls']==contract['subnode_limits']['model_calls']==1
    and 0<binding['limits']['time_s']<=limits.per_call_s and authority['tools']==[]
    and authority['network']=='none' and authority['network_allowlist']==[])
 run=core.get_run(contract['run_id'])
 _need(run['state'] in {'pending','running'} and run['account_id']==resources.principal.account_id
    and not core.cancellation_requested(contract['run_id']))
 frozen=runner._run_contexts.get(contract['run_id'])
 _need(frozen is not None and frozen['configuration_ref']==session['configuration_ref']
    and frozen['model_selection_profile_ref']==resources.exact_binding_refs['model_selection_profile_ref']
    and frozen['deployment_ref']==resources.exact_binding_refs['deployment_ref'])
 key=tuple(contract[name] for name in ('run_id','node_id','subnode_id','attempt_id'))
 with core._lock:
  _need(core.connection.execute('SELECT 1 FROM attempts WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?',key).fetchone() is None)
  run_used=core.connection.execute('SELECT count(*) FROM model_calls WHERE run_id=?',(contract['run_id'],)).fetchone()[0]
  node_used=core.connection.execute('SELECT count(*) FROM model_calls WHERE run_id=? AND node_id=?',(contract['run_id'],contract['node_id'])).fetchone()[0]
 for row in core.iter_records(run_id=contract['run_id'],kinds=('model-call-start','invocation-budget-reservation')):
  _need(row['record'].get('contract_ref')!=pin)
 parent=core.read_record(contract['node_contract_ref'],contract_id='node-execution-contract')
 calls=0;seconds=0;completed={row['record']['subnode_id'] for row in core.iter_records(run_id=contract['run_id'],kinds=('invocation-observation',))
   if row['record'].get('node_contract_ref')==contract['node_contract_ref']}
 for item in parent['subnodes']:
  if not item['required'] or item['subnode_id']==contract['subnode_id'] or item['subnode_id'] in completed:continue
  template=core.read_record(item['template_ref']);declaration=core.read_record(template['capsule_ref'],contract_id='capsule-declaration')
  budget=declaration['budget']['per_call'];count=budget['invocations'] if any(row['service_key']=='audited_model_bridge' for row in declaration['needs']['injects']) else 0
  duration=budget['wall_s']
  if item['role']=='verifier':
   profile=core.read_record(template['checking_profile_ref'],contract_id='checking-profile');_need(count==profile['model_call_limit']==1)
   duration=min(duration,profile['time_s'])
  calls+=count;seconds+=duration
 began=runner._run_started.get(contract['run_id']);_need(type(began) in (int,float))
 now=time.monotonic();elapsed=now-began
 node_began=runner._node_started.get((contract['run_id'],contract['node_id']),now)
 _need(frozen['run_limits']['model_calls']-run_used>=calls+1 and parent['node_limits']['model_calls']-node_used>=calls+1
    and frozen['run_limits']['time_s']-elapsed>seconds and parent['node_limits']['time_s']-(now-node_began)>seconds)
 return [pin,contract['node_contract_ref']]


class RuntimeReadiness:
 """Construct once beside actual resources, never from a submitted job field."""
 def __init__(self,store,resources,native_lease,worker,custodian,*,binding):
  self.store,self.resources,self.lease,self.worker,self.custodian=store,resources,native_lease,worker,custodian
  self.binding=binding

 async def inspect(self,job,*,job_ref=None):
  from .session_policy import _contracts
  validate_private('urn:ai4r:private:rsi-session-job:2',job)
  session=self.store.get(job['session_ref']);_contracts().validate('rsi-session',session)
  _need(job['session_ref'] in self.binding['approved_session_refs'])
  findings=[];target_ref=session['target_profile_ref'];worker_ref=job['worker_profile_ref']
  async def security():
   from jiuwenswarm.research.contracts.rsi_installation import installed_consumer_qualification
   from .qualification import require_qualification
   authority=installed_consumer_qualification(self.store)
   installation=getattr(authority,'installation',None)
   key=self.resources.operator.snapshot()['rsi']
   import base64
   expected=base64.urlsafe_b64decode(key['custodian_public_key']+'='*(-len(key['custodian_public_key'])%4)) if key['custodian_public_key'] else None
   _need(installation is not None and installation.qualification_ref==self.binding.get('security_qualification_ref')
      and installation.public_key==expected and installation.key_id==key['custodian_key_id'])
   proof=await asyncio.to_thread(require_qualification,authority,'session_start',session_ref=job['session_ref'],worker_profile_ref=worker_ref)
   return [proof['qualification_ref'],proof['scope_ref']]
  await _check(findings,'IF015_AUTHORITY',security)
  def frozen():
   target=self.store.get(target_ref);parent=self.store.get(session['parent_declaration_ref'])
   freeze_profile(target,parent,_contracts().validate)
   _need(self.resources.ready and session['configuration_ref']==self.binding['exact_binding_refs']['configuration_ref'])
   from .worker import validate_profile
   worker=validate_profile(self.store.get(worker_ref))
   _need(worker['schema']=='ai4r-rsi-worker-profile:3' and worker['session_ref']==job['session_ref']
      and worker['target_ref']==target_ref and worker['parent_ref']==target['parent_ref']
      and worker_ref==self.binding['worker']['profile_ref'] and worker['target_kind']==job['target_kind'])
   _need(session['started_by']==self.binding['principal']['account_id'] and session['parent']=={'cc_name':parent['identity']['name'],
      'cc_version':parent['identity']['version_label'],'declaration_sha256':session['parent_declaration_ref']['sha256']})
   _need(all(session[key]==target[key] for key in ('configuration_ref','improver_ref','scoring_adapter_ref')))
   limits=Limits.from_mapping(session['limits'])
   _need(session['pass_count_repeats']==1 and worker['memory_mb']<=target['limits']['memory_mb']
      and worker['timeout_s']<=min(target['limits']['time_s'],limits.per_call_s)
      and len(job['proposer_contract_refs'])==limits.max_attempts)
   core=self.resources.store
   for pin in job['proposer_contract_refs']:
    proposal=core.read_record(pin,contract_id='subnode-execution-contract')
    _need(core.record_kind(pin)=='subnode-execution-contract' and proposal['configuration_ref']==session['configuration_ref'])
    self.resources.runner._require_child_authority(pin,proposal)
    self.resources.runner._require_check_assets(proposal)
    key=tuple(proposal[name] for name in ('run_id','node_id','subnode_id','attempt_id'))
    with core._lock:
     _need(core.connection.execute('SELECT 1 FROM attempts WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?',key).fetchone() is None)
   entry=self.resources.composition.library.get(session['parent']['cc_name'],session['parent']['cc_version'])
   admitted=self.resources.store.read_record(entry['admission_ref'],contract_id='library-admission')
   _need(entry['declaration_ref']==session['parent_declaration_ref'] and admitted['status']=='admitted'
      and worker['memory_mb']<=admitted['memory_mb'])
   from .readiness import _path,_regular
   from .profiles import safe_path
   root=_path(self.binding['parent_directory'])
   expected={row['path']:row['sha256'] for row in parent['identity']['body']}
   for dependency in parent['needs']['external']:
    pin=dependency.get('pin')
    if isinstance(pin,dict) and set(pin)=={'ref','sha256'}:expected[pin['ref']]=pin['sha256']
   actual={path.relative_to(root).as_posix():path for path in root.rglob('*') if path.is_file() or path.is_symlink()}
   _need(set(actual)==set(expected))
   for name,path in actual.items():
    safe_path(name);_need(hashlib.sha256(_regular(path,uid=(0,12001))).hexdigest()==expected[name])
   FinalBudget.for_session(session,self.store,worker_profile=worker)
   self.store.read(target['parent_ref'])
   return [target_ref,worker_ref]
  await _check(findings,'FROZEN_TARGETS',frozen)
  def opportunity():
   from .opportunity import validated_preparation,_prerequisite_decision
   facts=validated_preparation(self.store,job['preparation_ref'],approved_preparation_refs=self.binding['approved_preparation_refs'],profile_ref=target_ref,parent=session['parent'])
   _need(facts['preparation']['worker_profile_ref']==worker_ref and _prerequisite_decision(facts)[0] is None)
   return [job['preparation_ref'],facts['preparation']['review_ref']]
  await _check(findings,'OPPORTUNITY_PREPARATION',opportunity)
  async def worker():
   value=await self.worker.prerequisites()
   _need(value.get('ready') is True and value.get('worker_uid')==12003 and worker_ref in value.get('profile_refs',[])
      and value.get('limitations')==[])
   return [worker_ref]
  await _check(findings,'WORKER_RUNTIME',worker)
  async def custodian():
   value=await self.custodian.readiness(job['session_ref'])
   validate_report(value)
   _need(value['status']=='READY' and value['session_ref']==job['session_ref'] and value['target_profile_ref']==target_ref
      and value['worker_profile_ref']==worker_ref)
   return [pin for row in value['findings'] for pin in row['proof_refs']]
  await _check(findings,'CUSTODIAN_RUNTIME',custodian)
  async def model_runtime():
   from jiuwenswarm.research.fixed_subscription import deployment_backend,HOST_CODEX_BACKEND
   exact=self.resources.exact_binding_refs
   if deployment_backend(self.resources.store.read_record(exact['deployment_ref']))==HOST_CODEX_BACKEND:
    from .host_codex_backend import HostCodexSubscriptionService
    self.lease.assert_available();service=self.resources.bridge.subscription
    _need(type(service) is HostCodexSubscriptionService and not self.resources.bridge._active_calls
       and not self.resources.bridge._uncertain_runs and not service.active)
    return await service.readiness_proof(store=self.resources.store,deployment_ref=exact['deployment_ref'])
   return native_observation(self.resources,self.lease)
  await _check(findings,'MODEL_RUNTIME',model_runtime)
  await _check(findings,'DIAGNOSIS_RUNTIME',lambda:diagnosis_contract(self.resources,session,job))
  def history():
   self.lease.assert_available()
   return readonly_history(self.store,job['session_ref'],clearance_policy_ref=self.binding.get('clearance_policy_ref'),job_ref=job_ref)
  await _check(findings,'SESSION_HISTORY',history)
  report=_report('ai4r-rsi-runtime-readiness:1',job['session_ref'],target_ref,worker_ref,findings)
  validate_report(report)
  return report


class CustodianRuntimeReadiness:
 """Actual custodian-owned frozen runtime inspection with no fixture run."""
 def __init__(self,store,ledger,sessions,runtimes,manifest,*,manifest_ref,public_key,key_id,expected_qualification_ref=None):
  self.store,self.ledger,self.sessions,self.runtimes,self.manifest=store,ledger,sessions,runtimes,manifest
  self.manifest_ref,self.public_key,self.key_id=manifest_ref,public_key,key_id
  self.expected_qualification_ref=expected_qualification_ref

 async def inspect(self,session_ref):
  session=self.store.get(session_ref);sid=session['session_id']
  _need(self.sessions.get(sid)==session and sid in self.runtimes)
  runtime=self.runtimes[sid];worker=runtime.worker;worker_ref=worker.profile_ref
  target_ref=session['target_profile_ref'];target=self.store.get(target_ref);findings=[]
  async def binding():
   from jiuwenswarm.research.contracts.rsi_installation import installed_consumer_qualification
   from .qualification import require_qualification
   authority=installed_consumer_qualification(self.store)
   proof=await asyncio.to_thread(require_qualification,authority,'session_start',session_ref=session_ref,worker_profile_ref=worker_ref)
   installation=getattr(authority,'installation',None)
   _need(installation is not None and installation.public_key==self.public_key and installation.key_id==self.key_id)
   _need(self.expected_qualification_ref is None or installation.qualification_ref==self.expected_qualification_ref)
   _need(self.store.get(self.manifest_ref)==self.manifest and self.manifest['target_ref']==target_ref
      and runtime.session_ref==session_ref and runtime.target==target)
   row=self.ledger.db.execute('SELECT identity FROM fixtures WHERE identity=?',(self.manifest['fixture_identity'],)).fetchone()
   _need(row is not None);return [target_ref,proof['qualification_ref'],proof['scope_ref']]
  await _check(findings,'CUSTODIAN_BINDING',binding)
  def calibration():
   from .targets.ranking_preparation import verify_calibration2
   value=self.store.get(self.manifest['calibration_ref'])
   _need(value.get('schema')=='ai4r-rsi-calibration:2' and target['calibration_ref']==self.manifest['calibration_ref'])
   actual=verify_calibration2(value,target=target,manifest=self.manifest,store=self.store,public_key=self.public_key,key_id=self.key_id)
   _need(isinstance(actual,dict) and type(actual.get('known_bad_rejected')) is int and actual['known_bad_rejected']>=10
      and type(actual.get('known_good_qualified')) is int and actual['known_good_qualified']>=3
      and actual.get('measurable_headroom') is True)
   from .worker import validate_profile
   measured=validate_profile(self.store.get(actual['worker_profile_ref']))
   current=validate_profile(self.store.get(worker_ref))
   _need(measured['schema']==current['schema']=='ai4r-rsi-worker-profile:3'
      and all(measured[key]==current[key] for key in ('target_kind','process_policy','environment_ref','hardware_ref','memory_mb','pids_max','timeout_s')))
   return [self.manifest['calibration_ref']]
  await _check(findings,'CUSTODIAN_CALIBRATION',calibration)
  def budget():
   profile=self.store.get(worker_ref)
   _need(profile['schema']=='ai4r-rsi-worker-profile:3' and profile['session_ref']==session_ref and profile['target_ref']==target_ref)
   FinalBudget.for_session(session,self.store,worker_profile=profile,manifest=self.manifest)
   return [self.store.get(session['chain_root_ref'])['final_budget_ref']]
  await _check(findings,'CUSTODIAN_BUDGET',budget)
  async def worker_health():
   value=await worker.prerequisites()
   _need(value.get('ready') is True and value.get('worker_uid')==12003 and value.get('limitations')==[] and worker_ref in value.get('profile_refs',[]))
   return [worker_ref]
  await _check(findings,'CUSTODIAN_WORKER',worker_health)
  def history():
   _need(self.ledger.db.execute('SELECT 1 FROM sessions WHERE id=?',(sid,)).fetchone() is None)
   return []
  await _check(findings,'CUSTODIAN_HISTORY',history)
  report=_report('ai4r-rsi-custodian-readiness:1',session_ref,target_ref,worker_ref,findings)
  validate_report(report)
  return report
