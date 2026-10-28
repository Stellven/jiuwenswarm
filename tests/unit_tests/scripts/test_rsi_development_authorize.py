"""Truthful development authorization derivation; no Root or model effects."""
import copy
from datetime import datetime,timedelta,timezone
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).parents[3]
spec=importlib.util.spec_from_file_location('unit_development_authorize',ROOT/'deploy/m1/rsi_development_authorize.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
def ref(name):return {'id':name,'sha256':a.seed.digest(name.encode())}


def test_source_revision_changes_only_runner_binding_preserves_old_bytes():
    old={'id':'run','expires_at':'unchanged','worker':{'contract_ref':ref('old'),'memory_mb':128}}
    old_execution={'admin_runner_sha256':'a'*64,'maximum_jobs':24,'security':'UNQUALIFIED'}
    before=copy.deepcopy((old,old_execution))
    new=copy.deepcopy(old);new['worker']['contract_ref']=ref('new')
    execution=dict(old_execution,admin_runner_sha256='b'*64)
    a.validate_source_revision(new,execution,old,old_execution)
    assert (old,old_execution)==before
    for changed in (dict(new,expires_at='extended'),dict(new,worker=dict(new['worker'],memory_mb=256))):
        with pytest.raises(ValueError):a.validate_source_revision(changed,execution,old,old_execution)
    with pytest.raises(ValueError):a.validate_source_revision(new,dict(execution,maximum_jobs=25),old,old_execution)


def test_unissued_window_refresh_is_utc_and_bounded_without_budget_change():
    now=datetime.now(timezone.utc)
    old={'id':'run','expires_at':(now+timedelta(minutes=5)).isoformat(),'worker':{'contract_ref':ref('old')}}
    previous={'admin_runner_sha256':'a'*64,'maximum_jobs':24}
    current=dict(previous,admin_runner_sha256='b'*64)
    auth=dict(old,expires_at=(now+timedelta(minutes=12)).isoformat(),worker={'contract_ref':ref('new')})
    a.validate_source_revision(auth,current,old,previous)
    for expiry in ((now+timedelta(hours=2)).isoformat(),(now+timedelta(minutes=1)).isoformat(),
                   (now+timedelta(minutes=12)).replace(tzinfo=None).isoformat()):
        with pytest.raises(ValueError):a.validate_source_revision(dict(auth,expires_at=expiry),current,old,previous)


def test_window_only_renewal_preserves_source_execution_and_model_budget():
    now=datetime.now(timezone.utc)
    old={'id':'run','expires_at':(now+timedelta(minutes=2)).isoformat(),
         'worker':{'contract_ref':ref('same')},'limits':{'max_attempts':1,'session_query_limit':2}}
    execution={'admin_runner_sha256':'a'*64,'maximum_jobs':24}
    before=copy.deepcopy((old,execution))
    renewed=dict(old,expires_at=(now+timedelta(minutes=30)).isoformat())
    a.validate_source_revision(renewed,execution,old,execution)
    assert (old,execution)==before
    with pytest.raises(ValueError):a.validate_source_revision(old,execution,old,execution)
    with pytest.raises(ValueError):
        a.validate_source_revision(dict(renewed,limits={'max_attempts':2,'session_query_limit':3}),execution,old,execution)


@pytest.mark.parametrize('fault',[None,'promoted-old-envelope','image','parent'])
def test_derive_new_deferred_authority_keeps_old_envelope_observation_only(fault):
    id='unit-run';context=ref('context');interface=ref('interface');old=ref('old-envelope')
    paths={'isolation_root':'/isolated','core_root':'/isolated/core','input_root':'/isolated/input','account_root':'/isolated/accounts',
        'record_root':'/isolated/records','native_lease_root':'/isolated/leases','work_root':'/isolated/work','parent_directory':'/isolated/parent',
        'native_scope_ref':ref('scope')}
    value={'id':id,'context_ref':context,'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        'seed_receipt':{'path':'/root/seed','sha256':'a'*64},'launch_guard_receipt':{'path':'/root/guard','sha256':'b'*64},
        'forbidden_roots':['/old/live'],'cgroup_root':'/run/ai4r-rsi-cgroups','evaluator_root':'/root/evidence'}
    exact={key:ref(key) for key in ('configuration_ref','model_selection_profile_ref','deployment_ref')}
    exact.update(workspace_id='local',protected_options={'development_builtin_catalog':False})
    prep={'id':id,'host_binding_ref':ref('raw-binding'),'host_id':'local-host','exact_binding_refs':exact,
        'work_capsule_refs':{'intent':ref('intent'),'verifier':ref('verifier')},'run_contexts':{'diagnosis':{},'proposal':{}},
        'public_original_refs':[ref('approved-public')],**{key:ref(key) for key in ('parent_declaration_ref','target_profile_ref',
            'visible_context_ref','preparation_ref','diagnosis_contract_ref','proposal_contract_ref','intake_ref')}}
    tests=[{'test_ref':ref('test-'+str(i)),'input_ref':ref('input-'+str(i))} for i in range(12)]
    data={context['id']:{'schema':'ai4r-rsi-root-helper-context:1','worker_image':a.IMAGE,'interface_ref':interface,
        'execution_contract_ref':old,'parent_ref':ref('parent'),'parent_declaration_ref':prep['parent_declaration_ref'],
        'environment_ref':ref('environment'),'hardware_ref':ref('hardware'),'worker_bounds':{'memory_mb':512,'pids_max':16,'timeout_s':1.0}},
        interface['id']:{'worker_program_ref':ref('program'),'target_kind':'ranking-v1'},
        old['id']:{'worker_program_ref':ref('program'),'execution_authorized':False,'qualification_required_before_effects':True},
        prep['target_profile_ref']['id']:{'parent_ref':ref('parent'),'parent_declaration_ref':prep['parent_declaration_ref'],
            'required_test_refs':[row['test_ref'] for row in tests],'mutable_paths':['ranking.py']},
        prep['visible_context_ref']['id']:{'required_test_refs':[row['test_ref'] for row in tests],'mandatory_fixtures':tests},
        prep['diagnosis_contract_ref']['id']:{'run_id':'diagnosis'},prep['proposal_contract_ref']['id']:{'run_id':'proposal'},
        prep['intake_ref']['id']:{'request_ref':ref('request')}}
    if fault=='promoted-old-envelope':data[old['id']]['execution_authorized']=True
    elif fault=='image':data[context['id']]['worker_image']='sha256:'+'0'*64
    elif fault=='parent':data[context['id']]['parent_ref']=ref('foreign')
    before=copy.deepcopy(data)
    class DB:
        def execute(self,*args):return self
        def fetchone(self):return ('unit-actor','local','pending')
    class Reader:
        db=DB()
        def get(self,pin):return data[pin['id']]
        def read(self,pin):return b'No gain established. Inspect public computation.'
    if fault:
        with pytest.raises(ValueError):a.derive(value,prep,{'id':id,'destination':paths},Reader())
    else:
        auth,execution,pin=a.derive(value,prep,{'id':id,'destination':paths},Reader())
        assert execution['observation_ref']==old and pin!=old and auth['worker']['contract_ref']==pin
        assert execution['maximum_jobs']==24 and execution['qualification_ref'] is None and execution['hidden_evaluation'] is False
        assert auth['worker']['memory_mb']==128 and auth['worker']['pids_max']==8 and auth['worker']['timeout_s']==5
        assert execution['security']=='UNQUALIFIED' and execution['security_campaigns']=='DEFERRED'
        assert pin not in auth['public_original_refs'] and data==before
