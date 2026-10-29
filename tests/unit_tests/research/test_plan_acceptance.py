"""Source-specific plan proof controls; no live Planner or calibration claim."""
import pytest
import inspect
from pathlib import Path
from jiuwenswarm.research.binding import Binder,SHARED_CHECKS
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.contracts import ResearchError

_BINDING_SOURCE = Path(inspect.getfile(Binder))
_STATIC_RUNNER_SOURCES = [_BINDING_SOURCE, *(
    _BINDING_SOURCE.with_name(name)
    for name in ('summary_planning.py', 'unified_planning.py', 'capability_planning.py')
)]


def static_proof(tmp_path):
    store=SQLiteRunStore(tmp_path);source=store.put_blob(b'protected static source');policy=store.put_blob(b'policy')
    plan={'plan_source':'static','source_ref':source,'policy_ref':policy,'brief_ref':store.put_blob(b'brief'),
        'library_snapshot_ref':store.put_blob(b'library'),'resource_inventory_ref':store.put_blob(b'resources'),'configuration_ref':store.put_blob(b'configuration')}
    checks=['template_structure',*SHARED_CHECKS]
    checkplan={'schema_version':'2.0.0','id':'static_checks','contract_ref':source,'node_contract_ref':source,
        'input_refs':[plan[k] for k in ['brief_ref','library_snapshot_ref','resource_inventory_ref','policy_ref']],
        'profile_ref':source,'policy_ref':policy,'mandatory_deterministic':checks,'mandatory_semantic':[],
        'runner_refs':[store.put_blob(path.read_bytes(),media_type='text/x-python')
                       for path in _STATIC_RUNNER_SOURCES],'subnode_id':None}
    pref=store.put_record('bound-check-plan',checkplan)
    result={'schema_version':'1.0.0','subject_ref':source,'check_plan_ref':pref,'results':[
        {'check_id':key,'outcome':'PASS','reason':'Controlled source proof vector','evidence_refs':[]} for key in checks]}
    plan['acceptance_ref']=store.put_record('deterministic-check-result',result)
    return store,Binder(store,None,None),plan,result,checkplan


def test_static_acceptance_is_exact_all_pass_result_without_gate_or_verifier(tmp_path):
    store,binder,plan,_,_=static_proof(tmp_path)
    binder.validate_acceptance(plan)
    assert not list(store.iter_records(kinds=('gate-decision','model-call')))


@pytest.mark.parametrize('fault',['failed','missing','duplicate','foreign_source','foreign_policy','foreign_inputs','foreign_runner','missing_runner','semantic','gate_as_static'])
def test_scheduler_plan_proof_refuses_incomplete_or_swapped_static_acceptance(tmp_path,fault):
    store,binder,plan,result,checkplan=static_proof(tmp_path)
    if fault=='failed':result['results'][0]['outcome']='FAIL'
    elif fault=='missing':result['results'].pop()
    elif fault=='duplicate':result['results'].append(result['results'][0])
    elif fault=='foreign_source':result['subject_ref']=store.put_blob(b'foreign template')
    elif fault=='foreign_policy':checkplan['policy_ref']=store.put_blob(b'foreign policy')
    elif fault=='foreign_inputs':checkplan['input_refs']=[]
    elif fault=='foreign_runner':checkplan['runner_refs']=[plan['source_ref']]
    elif fault=='missing_runner':checkplan['runner_refs'].pop()
    elif fault=='semantic':checkplan['mandatory_semantic']=['not_static']
    else:plan['acceptance_ref']=store.append_record('not-a-gate',{'action':'advance'})
    if fault!='gate_as_static':
        result['check_plan_ref']=store.put_record('bound-check-plan',checkplan)
        plan['acceptance_ref']=store.put_record('deterministic-check-result',result)
    with pytest.raises(ResearchError):binder.validate_acceptance(plan)


def test_static_proof_order_is_not_an_additional_source_requirement(tmp_path):
    store,binder,plan,result,checkplan=static_proof(tmp_path)
    result['results'].reverse();checkplan['mandatory_deterministic'].reverse()
    result['check_plan_ref']=store.put_record('bound-check-plan',checkplan)
    plan['acceptance_ref']=store.put_record('deterministic-check-result',result)
    binder.validate_acceptance(plan)
