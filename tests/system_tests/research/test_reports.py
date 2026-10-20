"""Status derivation only. Synthetic inputs cannot establish product acceptance."""
import hashlib
import json
from pathlib import Path
from scripts.research_reports import (derive_conclusions,validate_receipt,REPORT_NAMES,parse_native,derive_ac,source_identity)


def test_core_advanced_qa_full_are_distinct():
    checks={f'M1-SYSTEM/V{i:02}':{'status':'PASS'} for i in [1,2,3,4,5,6,8,9,15]}
    checks['M1-001/V01']={'status':'PASS'}
    core={key:[] for key in checks if key.startswith('M1-SYSTEM/')};core['M1-SYSTEM/V01']=['M1-001/V01']
    result=derive_conclusions(checks,{},all_work_complete=False,core_children=core)
    assert result['core_release']=='PASS'
    assert result['full_requested_delivery']=='INCOMPLETE'
    assert result['phase_2']=='INCOMPLETE' and result['phase_3']=='INCOMPLETE'
    assert derive_conclusions(checks,{},all_work_complete=False,core_children={})['core_release']=='INCOMPLETE'


def test_failed_blocked_stale_unrun_or_missing_never_pass():
    for status in ('FAIL','BLOCKED','STALE','NOT_RUN','N/A'):
        assert derive_ac({'required_checks':['M1-X/V01']},{'M1-X/V01':{'status':status}})['status']!='PASS'
    assert derive_ac({'required_checks':['missing']},{})['status']=='INCOMPLETE'


def test_native_matrix_missing_row_is_a_coverage_gap(tmp_path):
    feature=tmp_path/'M1-001';feature.mkdir()
    (feature/'spec.md').write_text('| M1-001/AC-001 | rule | required | BLOCK |\n')
    (feature/'plan.md').write_text('| M1-001/V01 | BLOCK | M1-001/AC-001 | fixture | expected | python -m pytest tests/test_one.py | resources |\n')
    (feature/'tasks.md').write_text('- [x] M1-001/T001 done\n')
    data=parse_native(feature)
    assert 'M1-001/AC-001' in data['acs'] and data['diagnostics']


def test_raw_junit_skips_and_zero_cases_refuse_claimed_pass(tmp_path):
    # This intentionally incomplete receipt must fail closed before any runtime
    # acceptance. Each missing identity/artifact remains an explicit diagnostic.
    check={'id':'M1-X/V01','level':'BLOCK','procedure_sha256':'a'*64}
    result=validate_receipt({'schema':'m1-verification-result:1','check_id':'M1-X/V01','outcome':'PASS'},
        check=check,root=tmp_path,candidate_id='candidate',source_sha='b'*64,interfaces={},native_pins={})
    assert result['status']!='PASS' and result['reasons']


def test_exact_five_lowercase_report_names():
    assert REPORT_NAMES==('phase_1_completion_report.md','phase_2_completion_report.md','phase_3_completion_report.md','m1_implementation_report.md','m1_final_test_report.md')


def test_added_consumed_interface_cannot_disappear_from_canonical_index():
    from scripts.research_reports import interface_index
    register='| M1-IF-001 / r2 | owner | M1-001 | consumer | boundary |\n'
    revisions,owners,diagnostics=interface_index(register,{'M1-IF-001','M1-IF-013'})
    assert revisions=={'M1-IF-001':'r2'} and owners=={'M1-IF-001':'M1-001'}
    assert 'Canonical interface missing from TASKS: M1-IF-013' in diagnostics
    assert interface_index(register+register,{'M1-IF-001'})[2]==['Duplicate interface definition M1-IF-001']


def test_valid_receipt_and_independent_mutations(tmp_path):
    from copy import deepcopy
    check={'id':'M1-001/V01','level':'BLOCK','procedure_sha256':'a'*64}
    assertion_manifest={'id':'independent_expected_cases','check_id':check['id'],'procedure_sha256':'a'*64,'required_dependency_mode':'local_real',
        'required_assertion_ids':['exact_source_constraint'],'required_case_ids':['source_checks::test_expected']}
    xml=b'<testsuite tests="1"><testcase classname="source_checks" name="test_expected"/></testsuite>'
    rows=[]
    for kind,name,raw in [('junit','junit.xml',xml),('assertion_manifest','assertions.json',json.dumps(assertion_manifest).encode()),('stdout','stdout.log',b'controlled status-fixture command output')]:
        (tmp_path/name).write_bytes(raw);rows.append({'kind':kind,'path':name,'sha256':hashlib.sha256(raw).hexdigest()})
    receipt={'schema':'m1-verification-result:1','check_id':check['id'],'outcome':'PASS','candidate_id':'candidate',
        'source_baseline_sha256':'b'*64,'procedure_sha256':'a'*64,'interface_revisions':{},'native_pins':{},'command':['python','-m','pytest'],'cwd':'/workspace',
        'started_at':'2026-10-16T00:00:00Z','ended_at':'2026-10-16T00:00:01Z','environment':{'platform':'linux/amd64','image_digest':'sha256:'+'c'*64},
        'dependency_mode':'local_real','artifacts':rows,'fixture_pins':{'independent_expected_cases':rows[1]['sha256']},'profile_pins':{'test_profile':'d'*64},
        'assertions':{'expected':1,'observed':1,'required_ids':['exact_source_constraint'],'passed_ids':['exact_source_constraint']}}
    args=dict(check=check,root=tmp_path,candidate_id='candidate',source_sha='b'*64,interfaces={},native_pins={})
    assert validate_receipt(receipt,**args)['status']=='PASS'
    for key,value in [('candidate_id','old'),('source_baseline_sha256','old'),('interface_revisions',{'M1-IF-001':'r2'}),('dependency_mode','mock'),('profile_pins',{}),('assertions',{'expected':0,'observed':0})]:
        bad=deepcopy(receipt);bad[key]=value;assert validate_receipt(bad,**args)['status']!='PASS'
    for xml in [b'<testsuite tests="0"/>',b'<testsuite><testcase classname="source_checks" name="test_expected"><skipped/></testcase></testsuite>']:
        (tmp_path/'junit.xml').write_bytes(xml);receipt['artifacts'][0]['sha256']=hashlib.sha256(xml).hexdigest()
        assert validate_receipt(receipt,**args)['status']!='PASS'


def test_supplied_source_byte_change_is_reported(tmp_path):
    program=tmp_path/'program';program.mkdir();original=b'original exact bytes\n';source=tmp_path/'source.txt';source.write_bytes(original)
    pin={'path':'source.txt','bytes':len(original),'sha256':hashlib.sha256(original).hexdigest()}
    (program/'source-baseline.json').write_text(json.dumps({'architecture':{'files':[pin]},'prd':pin,'qa':[],'invoked_prompt':pin}))
    assert source_identity(tmp_path,program)[1]==[]
    source.write_bytes(original[:-1]);assert 'source.txt' in source_identity(tmp_path,program)[1]


def test_native_expected_outcome_remains_available_for_qa_reporting(tmp_path):
    feature=tmp_path/'M1-QA';feature.mkdir()
    (feature/'TASK.md').write_text('owner')
    (feature/'spec.md').write_text('| M1-QA/AC-001 | source rule | required | BLOCK |\n')
    (feature/'plan.md').write_text('| M1-QA/V04 | BOUNDARY | M1-QA/AC-001 | exact frozen case | Actual original bytes and zero extra effects | python -m pytest tests/test_one.py | actual independent fixture |\n')
    (feature/'tasks.md').write_text('- [ ] M1-QA/T001 construct case\n')
    check=parse_native(feature)['checks']['M1-QA/V04']
    assert check['expected_outcome']=='Actual original bytes and zero extra effects'


def test_qa_report_distinguishes_frozen_required_assertions_and_unrun_observation():
    from scripts.research_reports import render_report
    status={'candidate_id':'frozen-candidate','conclusions':{'four_case_qa':'INCOMPLETE'},
        'counts':{'features':1,'acceptance_criteria':1,'checks':1,'work_completed':0,'work_items':1},
        'checks':{},'components':{},'diagnostics':[],'limitations':[],
        'qa_cases':{'capsule':{'implementation':'incomplete_or_not_recorded','execution':'INCOMPLETE',
            'required_checks':['M1-QA/V04'],'required_assertions':{'M1-QA/V04':'Actual original bytes and zero extra effects'},
            'assertions':{'M1-QA/V04':None},'evidence':[],'remaining_gaps':['M1-QA/V04: NOT_RUN']}}}
    report=render_report('m1_final_test_report.md',status)
    assert 'Actual original bytes and zero extra effects' in report
    assert 'Assertions not executed' in report and 'M1-QA/V04: NOT_RUN' in report
    assert 'capsule | incomplete_or_not_recorded | INCOMPLETE' in report
    status['qa_cases']['capsule']['assertions']['M1-QA/V04']={'expected':2,'observed':1,'passed_ids':['original_bytes']}
    report=render_report('m1_final_test_report.md',status)
    assert 'original_bytes' in report and '"observed": 1' in report
    assert 'capsule | incomplete_or_not_recorded | INCOMPLETE' in report
