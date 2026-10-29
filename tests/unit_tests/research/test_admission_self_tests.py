"""Admission cannot replace actual confined self-test evidence with booleans."""
import pytest
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


@pytest.mark.parametrize('observed',[{'confined':True,'end_state':'pass'},True,None,{'id':'missing','sha256':'0'*64}])
def test_self_test_consumer_requires_original_protected_execution_capture(tmp_path,observed):
    from jiuwenswarm.research.checks.admission import verify_self_test
    store=SQLiteRunStore(tmp_path);body=store.put_blob(b'print("fixture")')
    test={'id':'declared_test','kind':'command','ref':{'ref':'test.py','sha256':body['sha256']},'expects':'pass'}
    declaration=store.put_blob(b'original declaration')
    with pytest.raises(ResearchError):verify_self_test(store,test,declaration,{'test.py':body},observed)
    assert not list(store.iter_records(kinds=('library-admission','activation-record')))


@pytest.mark.parametrize('fault',[None,'duplicate_dimension','duplicate_anchor','duplicate_dependency'])
def test_screening_rubric_admission_uses_source_set_invariants_without_order_requirement(fault):
    import json
    from importlib.resources import files
    from jiuwenswarm.research.checks.admission import rubric_checks
    value=json.loads(files('jiuwenswarm.research').joinpath('resources/capsules/screening_rubric.json').read_text('utf-8'))
    value['dimensions'].reverse()
    if fault=='duplicate_dimension':value['dimensions'][1]=value['dimensions'][0]
    elif fault=='duplicate_anchor':value['dimensions'][0]['anchors'][1]=value['dimensions'][0]['anchors'][0]
    elif fault=='duplicate_dependency':value['forbidden_dependencies'].append(value['forbidden_dependencies'][0])
    rows=rubric_checks(json.dumps(value).encode())
    assert all(row['outcome']=='PASS' for row in rows) is (fault is None)


@pytest.mark.asyncio
@pytest.mark.parametrize('adapter_unbuilt',[False,True])
async def test_library_binds_provider_to_authenticated_actual_admission_memory(tmp_path,adapter_unbuilt):
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research.state import json_bytes
    from tests.unit_tests.research.test_check_asset_admission import prepared
    store,_,actor,asset=prepared(tmp_path);calls=[]
    class Provider:
        def for_admission(self,observed_actor,memory_mb):
            calls.append((observed_actor,memory_mb))
            async def execute(test,declaration_ref,body_refs):
                calls.append((test,declaration_ref,body_refs))
                if adapter_unbuilt:raise ResearchError('self_test_adapter_unbuilt','Explicit unit unavailable adapter')
                return None
            return execute
    library=LibraryService(store,self_test_provider=Provider())
    declaration=store.read_record(asset['declaration_ref']);body_refs=dict(asset['body_refs'])
    test_ref=store.put_blob(b'print("must actually invoke candidate")\n');body_refs['admission_test.py']=test_ref
    declaration['identity']['body'].append({'path':'admission_test.py','sha256':test_ref['sha256']})
    declaration['guarantees']['self_tests']=[{'id':'actual_test','kind':'command','ref':{'ref':'admission_test.py','sha256':test_ref['sha256']},'expects':'pass'}]
    ref=store.put_blob(json_bytes(declaration))
    result=await library.admit(ref,body_refs,actor,memory_mb=137)
    assert calls[0]==(actor,137) and calls[1][1:]==(ref,body_refs)
    assert store.read_record(result)['status']=='blocked'
    assert not list(store.iter_records(kinds=('activation-record',)))


@pytest.mark.asyncio
async def test_admission_authorization_is_finite_root_only_and_missing_provider_blocks(monkeypatch):
    from types import SimpleNamespace
    from jiuwenswarm.research import native_ports
    ports=native_ports.NativePorts.__new__(native_ports.NativePorts)
    ports.admission_tests=None
    with pytest.raises(ResearchError):ports.authorize_admission_self_test({'job_ref':{'id':'job','sha256':'a'*64}})
    received=[]
    ports.admission_tests=SimpleNamespace(authorize=lambda ref:received.append(ref) or {'job_ref':ref})
    ref={'id':'job','sha256':'a'*64}
    assert ports.authorize_admission_self_test({'job_ref':ref})=={'job_ref':ref}
    with pytest.raises(ResearchError):ports.authorize_admission_self_test({'job_ref':ref,'authorized':True})
    assert received==[ref]
    captured={}
    class Server:
        def __init__(self,*args,**kwargs):captured.update(kwargs)
        async def start(self):pass
    monkeypatch.setattr(native_ports,'PrivateRPCServer',Server)
    ports.authorization_server=None;ports.root=__import__('pathlib').Path('/private');ports.uid=10001;ports.session={}
    runner=SimpleNamespace(**{key:lambda payload:None for key in ['authorize_model_context','authorize_model_dispatch','authorize_executor_binding','authorize_containment']})
    await ports.bind_runner(runner)
    assert captured['operation_uids']['authorize_admission_self_test']=={0}
    assert captured['handlers']['authorize_admission_self_test']==ports.authorize_admission_self_test


def self_test_capture_fixture(tmp_path):
    """Explicit forged-kernel unit data; never runtime or calibration proof."""
    from tests.unit_tests.research.test_admission_executor import provider_fixture
    from jiuwenswarm.research.state import json_bytes,utc_now
    store,provider,actor,declaration,bodies,test=provider_fixture(tmp_path)
    job_ref=provider.issue(test,declaration,bodies,actor=actor,memory_mb=64);job=store.read_record(job_ref)
    value={'time_s':1,'model_calls':0,'memory_mb':1};output=store.put_blob(json_bytes(value))
    probe=store.put_blob(json_bytes({'ready':True,'executor_uid':10002,'executor_gid':10002,'cap_effective':'0',
        'no_new_privileges':'1','network':'none','denied_paths':{'protected_state':True}}))
    def receipt(identity,payload):
        return store.append_record('admission-self-test-execution',{'job_id':identity,'contract_ref':job_ref,
            'observed_runtime':True,'termination_reason':'completed','exit_code':0,'wall_time_s':0.01,'timeout_s':2,
            'stdout_ref':store.put_blob(json_bytes(payload)),'stderr_ref':store.put_blob(b''),
            'observed_limits':{'network':'none','memory_max':str(64*1024*1024),'pids_max':'32','isolation_probe_ref':probe}})
    response={'end_state':'pass','outputs':{'result':value},'reason_code':None}
    candidate=store.append_record('admission-self-test-candidate-execution',{'schema':'ai4r-admission-self-test-candidate-execution:1',
        'id':'unit-candidate','job_ref':job_ref,'declaration_ref':declaration,'body_refs':bodies,
        'input_ref':store.put_blob(json_bytes({'sample':value})),'execution_receipt_ref':receipt('candidate',response),
        'end_state':'pass','output_refs':{'result':output},'reason_code':None,'recorded_at':utc_now()})
    driver=receipt('driver',dict(response,candidate_call_id=candidate['id']))
    proof={'schema':'ai4r-admission-self-test-result:1','id':'unit-result','declaration_ref':declaration,'test_id':test['id'],
        'test_ref':bodies[test['ref']['ref']],'body_refs':bodies,'configuration_ref':provider.configuration_ref,
        'job_ref':job_ref,'execution_receipt_ref':driver,'driver_execution_ref':driver,'end_state':'pass','output_refs':[output],
        'reason_code':None,'candidate_execution_refs':[candidate],'model_call_refs':[],'recorded_at':utc_now()}
    return store,actor,test,declaration,bodies,proof


@pytest.mark.parametrize('fault',[None,'candidate_missing','foreign_candidate','driver_mismatch','driver_only',
    'wrong_port','request_actor','kernel_caps','malformed_probe','candidate_report'])
def test_if013_consumer_recomputes_actual_candidate_driver_and_kernel_joins(tmp_path,fault):
    from jiuwenswarm.research.checks.admission import verify_self_test
    from jiuwenswarm.research.state import json_bytes
    store,actor,test,declaration,bodies,proof=self_test_capture_fixture(tmp_path)
    if fault=='candidate_missing':proof['candidate_execution_refs']=[]
    elif fault in {'foreign_candidate','wrong_port','candidate_report'}:
        original=proof['candidate_execution_refs'][0];candidate=store.read_record(original)
        if fault=='foreign_candidate':candidate['declaration_ref']=proof['test_ref']
        elif fault=='wrong_port':candidate['output_refs']={'other':candidate['output_refs']['result']}
        else:
            receipt=store.read_record(candidate['execution_receipt_ref'])
            receipt['stdout_ref']=store.put_blob(json_bytes({'end_state':'pass','outputs':{},'reason_code':None}))
            candidate['execution_receipt_ref']=store.append_record('admission-self-test-execution',receipt)
        candidate['id']+=':changed';proof['candidate_execution_refs']=[store.append_record('admission-self-test-candidate-execution',candidate)]
    elif fault in {'driver_mismatch','driver_only','kernel_caps','malformed_probe'}:
        receipt=store.read_record(proof['driver_execution_ref'])
        if fault=='driver_mismatch':receipt['stdout_ref']=store.put_blob(json_bytes({'end_state':'pass','outputs':{},'reason_code':None,'candidate_call_id':'unit-candidate'}))
        elif fault=='driver_only':proof['candidate_execution_refs']=[proof['driver_execution_ref']]
        else:
            probe=store.read_record(receipt['observed_limits']['isolation_probe_ref'])
            probe['cap_effective']='1' if fault=='kernel_caps' else 'malformed'
            receipt['observed_limits']['isolation_probe_ref']=store.put_blob(json_bytes(probe))
        proof['execution_receipt_ref']=proof['driver_execution_ref']=store.append_record('admission-self-test-execution',receipt)
    elif fault=='request_actor':
        job=store.read_record(proof['job_ref']);request=store.read_record(job['admission_request_ref']);request['actor_id']='foreign'
        request['id']+=':changed';job['admission_request_ref']=store.append_record('admission-self-test-request',request);job['id']+=':changed'
        proof['job_ref']=store.append_record('admission-self-test-job',job)
    ref=store.append_record('admission-self-test-result',proof)
    if fault is None:assert verify_self_test(store,test,declaration,bodies,ref,memory_mb=64,actor=actor)==proof
    else:
        with pytest.raises(ResearchError):verify_self_test(store,test,declaration,bodies,ref,memory_mb=64,actor=actor)
