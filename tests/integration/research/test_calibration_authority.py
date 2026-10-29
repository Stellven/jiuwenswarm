"""Actual IF014 OS command/native-model boundary; external resources are mandatory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


def test_actual_operator_calibration_requires_original_native_calls_and_separate_asset_admissions(tmp_path):
    raw=os.environ.get('AI4R_CALIBRATION_ACTION_REF')
    if not raw:pytest.fail('BLOCKED: actual independently preregistered calibration action/profile/context/native model resources are required; no required skip')
    if os.geteuid()!=0:pytest.fail('BLOCKED: the finite OS Library command must enter as the actual operator before dropping permanently to APP UID')
    action=json.loads(raw)
    command=[sys.executable,'-m','jiuwenswarm.research.library_operator','calibrate-checks','--request-ref',json.dumps(action)]
    completed=subprocess.run(command,capture_output=True,text=True,timeout=3600)
    assert completed.returncode==0,('Actual finite calibration operation did not qualify both assets',completed.returncode)
    result=json.loads(completed.stdout)
    assert result['status']=='completed' and result['bundle_admission_ref'] and result['criteria_admission_ref']
    # Independently re-open as the permanent APP identity; never create root-
    # owned SQLite metadata or consume a producer's PASS boolean.
    proof_script=r'''
import json,os,sys
from pathlib import Path
os.setgroups([13000]);os.setresgid(10001,10001,10001);os.setresuid(10001,10001,10001)
from jiuwenswarm.research.state import SQLiteRunStore,json_bytes
from jiuwenswarm.research.checks.assets import CheckAssetAdmissions
store=SQLiteRunStore(os.environ['JIUWENSWARM_M1_STATE'],recover=False,input_root='/workspace/input')
result=json.loads(sys.argv[1]);owner=CheckAssetAdmissions(store)
bundle=store.read_record(result['bundle_admission_ref']);criteria=store.read_record(result['criteria_admission_ref'])
assert bundle['asset_kind']=='bundle' and criteria['asset_kind']=='criteria'
assert bundle['status']==criteria['status']=='admitted'
assert bundle['calibration_profile_ref']==criteria['calibration_profile_ref']
owner.require(bundle['closure']['bundle_ref'],criteria['closure']['profile_ref'])
profile,closure,registration=owner._registered(bundle['calibration_profile_ref'])
calls=[]
for ref in result['measurement_refs']:
    measurement=store.read_record(ref)
    case=next(case for case in profile['cases'] if case['case_id']==measurement['case_id'])
    assert measurement['status']=='matched' and owner._outcomes(profile,case,measurement['result'],registration)
    if case['asset_kind']=='criteria':
        assert len(measurement['result']['model_call_refs'])==1
        call_ref=measurement['result']['model_call_refs'][0];call=store.read_record(call_ref,contract_id='model-call')
        assert call['observed_runtime'] is True and call['outcome']=='completed' and call['call_function']=='verifier'
        traces=[ref for ref in call['evidence_refs'] if store.record_kind(ref)=='native-governed-trace']
        assert len(traces)==1 and store.read_record(traces[0])['status']=='completed'
        summary=store.read_record(traces[0]);assert summary['event_refs']
        for event_ref in summary['event_refs']:
            event=store.read_record(event_ref);assert event['scope']==summary['scope'] and store.read_blob(event['raw_ref'])
        calls.append(call_ref)
assert len(calls)==sum(case['asset_kind']=='criteria' for case in profile['cases'])
print(json.dumps({'request_ref':result['calibration_request_ref'],'bundle_admission_ref':result['bundle_admission_ref'],
    'criteria_admission_ref':result['criteria_admission_ref'],'model_call_refs':calls,'measurement_refs':result['measurement_refs']}))
store.close()
'''
    checked=subprocess.run([sys.executable,'-c',proof_script,json.dumps(result)],capture_output=True,text=True,timeout=120)
    assert checked.returncode==0,'Independent original-evidence recomputation failed'
    proof=json.loads(checked.stdout)
    target=Path(os.environ.get('AI4R_EVIDENCE_DIR',str(tmp_path)))
    target.mkdir(parents=True,exist_ok=True)
    (target/'calibration-command.json').write_text(json.dumps({'command':command,'result':result,'proof':proof},indent=2),encoding='utf-8')
