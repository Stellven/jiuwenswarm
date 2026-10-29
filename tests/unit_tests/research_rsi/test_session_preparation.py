"""Offline compilation vectors; no fixture/model execution or admission claims."""
import copy
import json
import os
import sys

import pytest

from jiuwenswarm.research_rsi import session_preparation as compiler
from jiuwenswarm.research_rsi.records import RecordStore,encoded
from jiuwenswarm.research_rsi.session_policy import FinalBudget
from jiuwenswarm.research_rsi.process_policy import POLICY


def fixture(tmp_path,monkeypatch):
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    source=make_unit_package(tmp_path/'source')
    store=RecordStore(tmp_path/'private')
    for ident,row in source['store'].ref_index().items():
        pin={'id':ident,'sha256':row['sha256']};store.put_ref(pin,source['store'].read_blob(pin))
    target_ref=source['session']['target_profile_ref'];target=store.get(target_ref)
    unit=source['session']['configuration_ref']
    source['store'].close()
    if sys.platform!='linux' or not hasattr(os,'geteuid') or os.geteuid()!=12002:
        monkeypatch.setattr(compiler,'require_custodian_store',lambda value:value)
    partitions={}
    for split,count in [('development',2),('hidden_loop',20),('hidden_final',20),('platform',2)]:
        rows=[]
        for index in range(count):
            name=split+'-'+str(index)
            inputs=store.put({'scores':[dict(idea_id=name,novelty=1,feasibility=1,compute_alignment=1,eligible=True)]})
            expected=store.put({'ranking':[{'rank':1,'idea_id':name,'total':3}],'selected_idea_id':name})
            rows.append({'id':name,'input_ref':inputs,'expected_ref':expected})
        partitions[split]=rows
    manifest={'schema':'ai4r-rsi-fixtures:1','fixture_identity':'controlled:fixture','target_ref':target_ref,
        'partitions':partitions,'independent':False,'independence_evidence_ref':unit,'calibration_ref':target['calibration_ref']}
    manifest_ref=store.put(manifest)
    values={'target_ref':target_ref,'fixture_manifest_ref':manifest_ref,'session_id':'unit:offline-calibration',
        'started_by':'unit:operator','limits':dict(max_attempts=2,max_no_progress=2,wall_s=30,per_call_s=5,
            session_query_limit=3,lifetime_query_limit=3),
        'worker':dict(target_kind='ranking-v1',contract_ref=unit,environment_ref=unit,hardware_ref=unit,
            memory_mb=64,pids_max=32,timeout_s=.005,process_policy=POLICY),
        'hash_profile_ref':unit,'invocation_wall_s':.01,'evidence_wall_s':1,'frozen_at':'2026-10-25T00:00:00Z'}
    return store,values,manifest,target


def test_compilation_is_deterministic_exact_and_not_a_start_or_approval(tmp_path,monkeypatch):
    store,values,manifest,target=fixture(tmp_path,monkeypatch)
    try:
        result=compiler.compile_helper_session(store,**values)
        assert result['status']=='COMPILED_NOT_STARTED'
        assert result==compiler.compile_helper_session(store,**values)
        session=store.get(result['session_ref']);profile=store.get(result['worker_profile_ref'])
        assert session['target_profile_ref']==values['target_ref']
        assert session['parent_declaration_ref']==target['parent_declaration_ref']
        assert session['pass_count_repeats']==1 and profile['schema']=='ai4r-rsi-worker-profile:3'
        assert profile['session_ref']==result['session_ref'] and profile['process_policy']==POLICY
        assert store.get(result['genesis_ref'])['final_budget_ref']==result['final_budget_ref']
        budget=FinalBudget.for_session(session,store,worker_profile=profile,manifest=manifest)
        assert budget.hidden_final_units==20 and budget.mandatory_units==2 and budget.final_reserve_s==7
        assert budget.search_remaining(deadline=30,now=0)==22
        assert store.db.execute('SELECT count(*) FROM session_history').fetchone()[0]==0
        assert store.db.execute('SELECT count(*) FROM session_phases').fetchone()[0]==0
        assert not any(word in json.dumps(result) for word in ('case:','partitions','expected_ref','admitted'))
    finally:store.close()


def test_changed_actual_population_changes_reserve_and_requires_new_session_id(tmp_path,monkeypatch):
    store,values,manifest,_=fixture(tmp_path,monkeypatch)
    try:
        original=compiler.compile_helper_session(store,**values)
        changed=copy.deepcopy(manifest);row=copy.deepcopy(changed['partitions']['hidden_final'][-1])
        row.update(id='new-final-unit',input_ref=store.put({'scores':[dict(idea_id='new-final-unit',novelty=2,feasibility=2,compute_alignment=2,eligible=True)]}),
            expected_ref=store.put({'ranking':[{'rank':1,'idea_id':'new-final-unit','total':6}],'selected_idea_id':'new-final-unit'}))
        changed['partitions']['hidden_final'].append(row)
        changed_ref=store.put(changed)
        with pytest.raises(ValueError):compiler.compile_helper_session(store,**dict(values,fixture_manifest_ref=changed_ref))
        current=compiler.compile_helper_session(store,**dict(values,fixture_manifest_ref=changed_ref,session_id='unit:offline-operational'))
        assert current['session_ref']!=original['session_ref']
        assert store.get(current['final_budget_ref'])['hidden_final_units']==21
    finally:store.close()


def test_worker_execution_contract_and_frozen_interface_remain_distinct_pins(tmp_path,monkeypatch):
    store,values,_,target=fixture(tmp_path,monkeypatch)
    try:
        execution=store.put({'controlled':'separate protected worker execution envelope'})
        values['worker']['contract_ref']=execution
        result=compiler.compile_helper_session(store,**values)
        assert store.get(result['worker_profile_ref'])['contract_ref']==execution
        assert store.get(values['target_ref'])['frozen_contract_ref']==target['frozen_contract_ref']
        assert execution!=target['frozen_contract_ref']
    finally:store.close()


def test_session_identity_binding_survives_reopened_private_store(tmp_path,monkeypatch):
    store,values,_,_=fixture(tmp_path,monkeypatch)
    result=compiler.compile_helper_session(store,**values);root=store.root;store.close()
    store=RecordStore(root)
    try:
        assert compiler.compile_helper_session(store,**values)==result
        with pytest.raises(ValueError):
            compiler.compile_helper_session(store,**dict(values,frozen_at='2026-10-25T00:00:01Z'))
        assert store.db.execute('SELECT count(*) FROM session_compilations').fetchone()[0]==1
    finally:store.close()


@pytest.mark.parametrize('change',['margin','timeout','policy','missing_original','overlap'])
def test_inconsistent_or_underfunded_compilation_fails_before_session_records(tmp_path,monkeypatch,change):
    store,values,manifest,_=fixture(tmp_path,monkeypatch)
    try:
        if change=='margin':values['limits']['wall_s']=8
        elif change=='timeout':values['worker']['timeout_s']=.02
        elif change=='policy':values['worker']['process_policy']='caller-ready-flag'
        elif change=='missing_original':values['worker']['hardware_ref']={'id':'missing','sha256':'d'*64}
        else:
            manifest['partitions']['platform'][0]=copy.deepcopy(manifest['partitions']['development'][0])
            values['fixture_manifest_ref']=store.put(manifest)
        before=set(path.name for path in store.root.glob('*.json'))
        with pytest.raises((ValueError,FileNotFoundError)):compiler.compile_helper_session(store,**values)
        assert set(path.name for path in store.root.glob('*.json'))==before
    finally:store.close()


def test_compiler_never_executes_parent_source_and_preserves_original_aliases(tmp_path,monkeypatch):
    store,values,manifest,target=fixture(tmp_path,monkeypatch)
    try:
        original=store.read(target['parent_ref'])
        body=store.put_bytes(b'raise AssertionError("must never execute during compilation")\n'+original)
        parent=store.get(target['parent_declaration_ref'])
        for row in parent['identity']['body']:
            if row['path']==target['mutable_paths'][0]:row['sha256']=body['sha256']
        parent_ref=store.put(parent);target.update(parent_ref=body,parent_declaration_ref=parent_ref)
        target_ref=store.put(target);manifest['target_ref']=target_ref
        values.update(target_ref=target_ref,fixture_manifest_ref=store.put(manifest))
        result=compiler.compile_helper_session(store,**values)
        assert result['status']=='COMPILED_NOT_STARTED'
        assert store.read(body).startswith(b'raise AssertionError')
    finally:store.close()


def test_started_or_halted_session_cannot_be_relabelled_compiled_not_started(tmp_path,monkeypatch):
    store,values,_,_=fixture(tmp_path,monkeypatch)
    try:
        result=compiler.compile_helper_session(store,**values)
        context=store.put({'controlled':'original execution context'})
        store.begin_session_history(values['session_id'],result['session_ref'],context)
        with pytest.raises(ValueError):compiler.compile_helper_session(store,**values)
    finally:store.close()


def contract(store,unit,configuration,number):
    value={'schema_version':'1.0.0','id':'unit:contract-'+str(number),'run_id':'unit:run',
        'node_id':'unit-node','subnode_id':'call-'+str(number),'attempt_id':'unit-a'+str(number),'revision':1,
        'objective':'Controlled one-call contract; no admitted execution resources','requirement_ids':['unit'],
        'node_contract_ref':unit,'template_ref':unit,'checking_profile_ref':unit,'policy_ref':unit,'configuration_ref':configuration,
        'bindings':[{'id':'unit.binding','role':'work','declaration_ref':unit,'implementation_refs':[unit],
            'dependency_refs':[],'admission_ref':unit,'effective_authority':{'network':'none','network_allowlist':[],
                'resource_reads':[unit],'write_roots':[],'tools':[]},'limits':{'time_s':1,'model_calls':1,'memory_mb':64}}],
        'inputs':[{'name':'input','contract_id':'opaque-bytes','version':'1.0.0','required':True,'artifact_refs':[unit]}],
        'outputs':[{'name':'output','contract_id':'opaque-bytes','version':'1.0.0','required':True}],
        'input_refs':[unit],'required_outputs':['output'],'evidence_obligations':['captured_output'],
        'subnode_limits':{'time_s':1,'model_calls':1,'memory_mb':64}}
    compiler._contracts().validate('subnode-execution-contract',value)
    return store.put(value)


def test_job2_requires_approved_preparation_and_distinct_bounded_contracts(tmp_path,monkeypatch):
    from jiuwenswarm.research_rsi import opportunity
    store,values,manifest,target=fixture(tmp_path,monkeypatch)
    try:
        result=compiler.compile_helper_session(store,**values)
        prep=store.put({'controlled':'independently approved visible preparation placeholder'})
        def validated(*args,**kwargs):
            assert kwargs['approved_preparation_refs']==[prep]
            return {'preparation':{'worker_profile_ref':result['worker_profile_ref']}}
        monkeypatch.setattr(opportunity,'validated_preparation',validated)
        visible=store.put({'context':{'controlled':True},'required_test_refs':target['required_test_refs'],
            'mandatory_fixtures':[{'input_ref':manifest['partitions']['development'][0]['input_ref'],'test_ref':target['required_test_refs'][0]}]})
        calls=[contract(store,values['hash_profile_ref'],target['configuration_ref'],i) for i in range(3)]
        arguments=dict(session_ref=result['session_ref'],preparation_ref=prep,approved_preparation_refs=[prep],
            visible_context_ref=visible,diagnosis_contract_ref=calls[0],proposer_contract_refs=calls[1:],
            worker_profile_ref=result['worker_profile_ref'],fixture_identity=manifest['fixture_identity'],target_kind='ranking-v1')
        job_ref=compiler.assemble_job2(store,**arguments)
        job=store.get(job_ref)
        assert job['schema']=='ai4r-rsi-session-job:2' and 'opportunity_ref' not in job
        assert job['diagnosis_contract_ref']==calls[0]
        with pytest.raises(ValueError):compiler.assemble_job2(store,**dict(arguments,approved_preparation_refs=[]))
        with pytest.raises(ValueError):compiler.assemble_job2(store,**dict(arguments,diagnosis_contract_ref=calls[1]))
        with pytest.raises(ValueError):compiler.assemble_job2(store,**dict(arguments,fixture_identity='caller-reset-lineage'))
    finally:store.close()
