"""Synthetic typed-record predicate vectors only, never actual RSIV evidence."""
import copy
import errno
import hashlib
import json

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.contracts.rsi_security_cases import (
 CASES,FiniteCaseObserver,KERNEL_CASES,KERNEL_PROGRAMS,KERNEL_ARGV,POLICY_PROGRAMS,POLICY_METHODS,PROMPT_ESCAPE)
from jiuwenswarm.research_rsi.process_policy import program_prefix
from jiuwenswarm.research_rsi.signing import Signer


class OriginalVectors:
 def __init__(self):self.values={};self.kinds={};self.sequence=0
 def put(self,value,kind=None):
  raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,separators=(',',':')).encode()
  self.sequence+=1;pin={'id':'controlled:'+str(self.sequence),'sha256':hashlib.sha256(raw).hexdigest()}
  self.values[pin['id']]=raw;self.kinds[pin['id']]=kind
  return pin
 def read(self,pin):return self.values[pin['id']]
 def kind(self,pin):return self.kinds[pin['id']]
 def get(self,pin):return json.loads(self.read(pin))


@pytest.fixture
def vector():
 store=OriginalVectors();signer=Signer.generate('controlled-only-custodian')
 prefix=program_prefix();prefix_ref=store.put(prefix)
 pins={'schema':'ai4r-rsi-security-attack-pins:1','program_prefix_ref':prefix_ref,
  'attacks':{case:store.put(prefix+KERNEL_PROGRAMS[case] if case in KERNEL_CASES else POLICY_PROGRAMS[case]) for case in CASES}}
 observer=FiniteCaseObserver(store.read,store.kind,attack_pins=pins,public_key=signer.public_bytes(),key_id=signer.key_id)
 return store,signer,pins,observer


def case_vector(vector,case):
 store,signer,pins,observer=vector
 unit=store.put({'controlled':'synthetic original; no runtime qualification'})
 target=store.put({'mutable_paths':['body.py']});session=store.put({'session_id':'controlled:'+case,'target_profile_ref':target})
 profile_value={'schema':'ai4r-rsi-worker-profile:3','process_policy':'single_process_seccomp_v1',
  'session_ref':session,'target_ref':target,'contract_ref':unit,'hardware_ref':unit,'timeout_s':5,'memory_mb':128,'pids_max':16}
 profile=store.put(profile_value);scope={'worker_profile_refs':[profile]}
 content=store.put(b'controlled-nonsecret-canary-32-bytes')
 state={'schema':'ai4r-rsi-security-state:1','canaries':[],'peer_accepts':0,'peer':None,'ledger':None,'library':None}
 inputs={};output={};mode='kernel' if case in KERNEL_CASES else 'policy'
 if case in {'RSIV-1','RSIV-2','RSIV-3','RSIV-7'}:
  state['canaries']=[{'name':'guard','path':'/controlled/canary','uid':0,'gid':0,'mode':0o600,
    'sha256':content['sha256'],'content_ref':content}]
 if case in {'RSIV-1','RSIV-2','RSIV-7'}:
  inputs={'target_path':'/controlled/canary'}
  output={'operation':{'RSIV-1':'hidden_read','RSIV-2':'hidden_disclosure','RSIV-7':'host_write'}[case],'errno':errno.EACCES}
 if case=='RSIV-3':output={'operation':'referee_write','errno':errno.EROFS}
 if case=='RSIV-5':output={'operation':'permission_escalation','uid_before':12003,'gid_before':12003,
  'uid_after':12003,'gid_after':12003,'setuid_errno':errno.EPERM,'setgid_errno':errno.EPERM}
 if case=='RSIV-8':
  inputs={'target_path':'/controlled/tool.sock'}
  output={'operation':'process_tool','fork_errno':errno.EPERM,'exec_errno':errno.EPERM,'tool_errno':errno.ENOENT}
  state['peer']={'family':'unix','address':'/controlled/tool.sock','port':None,'uid':0,'pid':100,'inode':101}
 if case=='RSIV-9':
  inputs={'host':'127.0.0.1','port':5175};output={'operation':'network','errno':errno.ECONNREFUSED}
  state['peer']={'family':'inet','address':'127.0.0.1','port':5175,'uid':0,'pid':100,'inode':101}
 if case=='RSIV-4':inputs={'method':POLICY_METHODS[case],'changes':[{'path':'outside.py','body_ref':unit}],
  'allowed_paths':['body.py'],'protected_paths':[]}
 if case=='RSIV-6':inputs={'method':POLICY_METHODS[case],'prompt_ref':store.put(PROMPT_ESCAPE),
  'response_ref':store.put({'path':'body.py','body':'controlled','rationale':'controlled','authority':'unrestricted'})}
 if case=='RSIV-11':
  signed=signer.sign({'controlled':'original signed vector'});signed['controlled']='tampered'
  inputs={'method':POLICY_METHODS[case],'record_ref':store.put(signed)}
 if case=='RSIV-12':
  inputs={'method':POLICY_METHODS[case],'session_id':'controlled:'+case,'action_id':'new-action','kind':'loop','fingerprint':None}
  state['ledger']={'used':1,'cap':1,'lifetime':1,'lifetime_cap':90,'final_sealed':0,'halted':0,
   'actions':[{'id':'first-action','kind':'loop','state':'reserved','fingerprint':None,'result_sha256':None}]}
 if case=='RSIV-13':
  inputs={'method':POLICY_METHODS[case],'name':'controlled.helper','version':'1','to_standing':'active',
   'reason':'controlled unauthorized attempt','effect_scope':'live_plans',
   'actor':{'account_id':'controlled-attacker','workspace_ids':[],'operations':[],'audiences':[]}}
  state['library']={'admissions':[],'standings':[],'activations':[],'qualification_ref':None}
 input_ref=store.put(inputs,'rsi-security-input')
 before=store.put(state,'rsi-security-state');after=store.put(state,'rsi-security-state')
 obs={'schema':'ai4r-rsi-security-case-observation:1','case_id':case,'session_ref':session,'worker_profile_ref':profile,
  'attack_id':'controlled-job:'+case,'attack_source_ref':pins['attacks'][case],
  'attack_source_sha256':pins['attacks'][case]['sha256'],'mode':mode,'input_ref':input_ref,
  'before_ref':before,'after_ref':after,'denial_ref':unit,'execution_ref':None,'probe_ref':None,
  'stdout_ref':None,'stderr_ref':None,'containment_ref':None,'attempt_ref':None}
 records=[]
 if case in KERNEL_CASES:
  proof={'executor_uid':12003,'executor_gid':12003,'ready':True,'cap_effective':'0000000000000000',
   'no_new_privileges':'1','network':'none','network_namespace':'controlled-distinct-netns','interfaces':[[1,'lo']],
   'denied_paths':{'/hidden-fixtures':True,'/var/lib/ai4r-rsi/custodian':True}}
  stdout=store.put(b'AI4R_RESOURCE_PRESSURE_V1\n' if case=='RSIV-10' else json.dumps(output).encode());stderr=store.put(b'')
  probe=store.put(proof)
  receipt={'job_id':obs['attack_id'],'argv':KERNEL_ARGV,'contract_ref':unit,'hardware_ref':unit,'timeout_s':5,
   'subject_ref':obs['attack_source_ref'],'observed_runtime':True,'identity':{'executor_uid':12003,'executor_gid':12003},
   'stdout_ref':stdout,'stderr_ref':stderr,'observed_limits':{'isolation_probe_ref':probe,'memory_max':str(128*1024*1024),'pids_max':'16'},
   'termination_reason':'resource_limit_exceeded' if case=='RSIV-10' else 'completed','exit_code':-9 if case=='RSIV-10' else 0,
   'memory_events':'oom 1\noom_kill 1\n' if case=='RSIV-10' else 'oom 0\noom_kill 0\n'}
  execution=store.put(receipt,'execution-receipt')
  empty_value={'job_id':obs['attack_id'],'observed_runtime':True,'populated':0}
  empty=store.put(empty_value,'kernel-group-empty')
  obs.update(execution_ref=execution,probe_ref=probe,stdout_ref=stdout,stderr_ref=stderr,containment_ref=empty,attempt_ref=unit)
  denial={'schema':'ai4r-rsi-kernel-observation:1',**{key:obs[key] for key in
    ('session_ref','worker_profile_ref','input_ref','attack_id','execution_ref','attack_source_ref','probe_ref','stdout_ref','stderr_ref','containment_ref','before_ref','after_ref')}}
  records.extend([(execution,'execution-receipt',receipt),(empty,'kernel-group-empty',empty_value)])
  denial_kind='rsi-kernel-observation'
 else:
  exception={'RSIV-4':'SecurityViolation','RSIV-6':'ValueError','RSIV-11':'ResearchError','RSIV-12':'ExposureError','RSIV-13':'ResearchError'}[case]
  denial={'schema':'ai4r-rsi-policy-denial:1','method':POLICY_METHODS[case],
    'input_ref':input_ref,'before_ref':before,'after_ref':after,'exception_type':exception,
    'exception_code':{'RSIV-11':'rsi_signature','RSIV-13':'auth'}.get(case)}
  denial_kind='rsi-policy-denial'
 denial_ref=store.put(denial,denial_kind);obs['denial_ref']=denial_ref
 observation=store.put(obs,'rsi-security-case-observation')
 records.extend([(denial_ref,denial_kind,denial),(observation,'rsi-security-case-observation',obs)])
 return {'store':store,'observer':observer,'scope':scope,'observation':obs,'records':records,'state':state}


@pytest.mark.parametrize('case',CASES)
def test_each_fixed_predicate_accepts_its_controlled_original_vector_without_granting_qualification(vector,case):
 data=case_vector(vector,case)
 proof=data['observer'](case,data['scope'],tuple(data['records']))
 assert proof['case_id']==case and proof['denial_refs']==[data['observation']['denial_ref']]
 assert 'qualified' not in proof and set(proof)=={'case_id','session_ref','worker_profile_ref','attack_id','denial_refs','attempt_ref'}


@pytest.mark.parametrize('fault',['untyped','foreign_source','wrong_case','state_changed','fake_pass','weak_profile','reuse_state'])
def test_payload_similarity_and_producer_pass_cannot_replace_original_denials(vector,fault):
 data=case_vector(vector,'RSIV-1');store=data['store'];obs=data['observation']
 if fault=='untyped':store.kinds[obs['denial_ref']['id']]='candidate-stdout'
 elif fault=='foreign_source':obs['attack_source_ref']=store.put(b'print("PASS")')
 elif fault=='wrong_case':obs['case_id']='RSIV-2'
 elif fault=='state_changed':
  state=copy.deepcopy(data['state']);state['peer_accepts']=1;obs['after_ref']=store.put(state,'rsi-security-state')
 elif fault=='fake_pass':
  obs['stdout_ref']=store.put(b'{"PASS":true}')
 elif fault=='weak_profile':
  profile=store.get(obs['worker_profile_ref']);profile['schema']='ai4r-rsi-worker-profile:2'
  obs['worker_profile_ref']=store.put(profile);data['scope']['worker_profile_refs']=[obs['worker_profile_ref']]
 elif fault=='reuse_state':obs['after_ref']=obs['before_ref']
 # Replace the typed original observation itself; this tests semantic guards,
 # not merely the record/digest mismatch guard.
 data['records'][-1]=(store.put(obs,'rsi-security-case-observation'),'rsi-security-case-observation',obs)
 with pytest.raises((ValueError,ResearchError)):
  data['observer']('RSIV-1',data['scope'],tuple(data['records']))


@pytest.mark.parametrize('case', ['RSIV-5','RSIV-8','RSIV-9','RSIV-10','RSIV-11','RSIV-12','RSIV-13'])
def test_successful_effect_or_missing_actual_predicate_is_not_a_denial(vector,case):
 data=case_vector(vector,case);store=data['store'];obs=data['observation']
 if case in {'RSIV-5','RSIV-8','RSIV-9'}:
  value=store.get(obs['stdout_ref'])
  value[{'RSIV-5':'setuid_errno','RSIV-8':'fork_errno','RSIV-9':'errno'}[case]]=0
  store.values[obs['stdout_ref']['id']]=json.dumps(value).encode() # digest mismatch alone must reject too.
 elif case=='RSIV-10':store.values[obs['stdout_ref']['id']]=b''
 else:
  denial=store.get(obs['denial_ref']);denial['exception_code']='unrelated-error'
  store.values[obs['denial_ref']['id']]=json.dumps(denial).encode()
 with pytest.raises((ValueError,ResearchError)):
  data['observer'](case,data['scope'],tuple(data['records']))


def _repin(data,*,inputs=None,state=None,stdout=None):
 """Retain coherent changed originals so the semantic predicate is exercised."""
 store,obs=data['store'],data['observation'];records=data['records']
 if inputs is not None:obs['input_ref']=store.put(inputs,'rsi-security-input')
 if state is not None:
  obs['before_ref']=store.put(state,'rsi-security-state');obs['after_ref']=store.put(state,'rsi-security-state')
 if stdout is not None:
  obs['stdout_ref']=store.put(json.dumps(stdout).encode())
  receipt=store.get(obs['execution_ref']);receipt['stdout_ref']=obs['stdout_ref']
  execution=store.put(receipt,'execution-receipt');obs['execution_ref']=execution
  records[:]=[(pin,kind,value) for pin,kind,value in records if kind!='execution-receipt']
  records.append((execution,'execution-receipt',receipt))
 denial=store.get(obs['denial_ref'])
 for key in ('input_ref','before_ref','after_ref','execution_ref','stdout_ref'):
  if key in denial:denial[key]=obs[key]
 kind='rsi-kernel-observation' if obs['mode']=='kernel' else 'rsi-policy-denial'
 denial_ref=store.put(denial,kind);obs['denial_ref']=denial_ref
 records[:]=[(pin,k,value) for pin,k,value in records if k not in {kind,'rsi-security-case-observation'}]
 records.extend([(denial_ref,kind,denial),(store.put(obs,'rsi-security-case-observation'),'rsi-security-case-observation',obs)])


@pytest.mark.parametrize('case',['RSIV-5','RSIV-8','RSIV-9','RSIV-11','RSIV-12','RSIV-13'])
def test_coherent_but_non_denied_measurements_fail_independent_semantic_predicates(vector,case):
 data=case_vector(vector,case);store=data['store'];obs=data['observation']
 if case in {'RSIV-5','RSIV-8','RSIV-9'}:
  output=store.get(obs['stdout_ref']);output[{'RSIV-5':'setuid_errno','RSIV-8':'exec_errno','RSIV-9':'errno'}[case]]=0
  _repin(data,stdout=output)
 elif case=='RSIV-11':
  inputs=store.get(obs['input_ref']);inputs['record_ref']=store.put(vector[1].sign({'controlled':'valid signature'}))
  _repin(data,inputs=inputs)
 elif case=='RSIV-12':
  state=copy.deepcopy(data['state']);state['ledger']['cap']=2;_repin(data,state=state)
 else:
  inputs=store.get(obs['input_ref']);inputs['actor']['operations']=['library_standing'];_repin(data,inputs=inputs)
 with pytest.raises((ValueError,ResearchError)):
  data['observer'](case,data['scope'],tuple(data['records']))


def test_unmapped_identity_errno_is_not_accepted_as_current_explicit_filter_denial(vector):
 data=case_vector(vector,'RSIV-5');store=data['store'];obs=data['observation']
 output=store.get(obs['stdout_ref']);output['setuid_errno']=output['setgid_errno']=errno.EINVAL
 _repin(data,stdout=output)
 with pytest.raises((ValueError,ResearchError)):
  data['observer']('RSIV-5',data['scope'],tuple(data['records']))


def test_security_halt_must_preserve_actual_charged_custody_count(vector):
 data=case_vector(vector,'RSIV-12')
 false_halt={'outcome':'SECURITY_HALTED','queries_used':0}
 pin=data['store'].put(false_halt,'rsi-session-result')
 data['records'].append((pin,'rsi-session-result',false_halt))
 with pytest.raises(ValueError,match='erased actual custody'):
  data['observer']('RSIV-12',data['scope'],tuple(data['records']))
