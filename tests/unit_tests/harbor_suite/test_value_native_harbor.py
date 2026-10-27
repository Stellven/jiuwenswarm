import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.harbor_suite import value_native_harbor as native


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf-8')


def fixture(tmp_path):
    stage=tmp_path/'stage';stage.mkdir();(stage/'inputs').mkdir();(stage/'broker').mkdir()
    spec={'variant':'native','skill_dirs':[],'model':'gpt-6.1-sol','reasoning_effort':'medium',
          'task':'Produce the requested verdict from the public evidence.','max_model_calls':6}
    put(stage/'spec.json',spec);put(stage/'commands.json',{'run':['never executed in test']})
    runtime=stage/'runtime/benchmarks/harbor_suite/native_value.py';runtime.parent.mkdir(parents=True);runtime.write_text('# offline fixture')
    executable=tmp_path/'python.exe';executable.write_bytes(b'offline fixture executable')
    wrapper=tmp_path/'execute_native.py';wrapper.write_text('# offline fixture wrapper')
    task=tmp_path/'task';task.mkdir();(task/'instruction.md').write_text(spec['task'],encoding='utf-8')
    public=tmp_path/'export';public.mkdir();private=tmp_path/'private';private.mkdir()
    controls=[executable,wrapper,stage/'spec.json',stage/'commands.json',runtime]
    config={'schema':native.SCHEMA,'task_root':str(task),'staged_root':str(stage),'public_export':str(public),
            'private_control':str(private),'cwd':str(tmp_path),'command':[str(executable),'C:/execute_native.py','run','--staged','C:/stage'],
            'execute_script_host':str(wrapper),'execute_script_argument':'C:/execute_native.py','staged_argument':'C:/stage',
            'control_files':{str(f):native.pin(f) for f in controls},'expected_model':'gpt-6.1-sol','expected_effort':'medium',
            'task_sha256':hashlib.sha256(spec['task'].encode()).hexdigest(),'timeout_s':20}
    path=tmp_path/'host.json';put(path,config)
    taskmeta={'case_id':'ccv05-evaluate','variant_id':'primary','task_sha256':config['task_sha256'],
              'native_spec_sha256':native.pin(stage/'spec.json')['sha256'],'expected_model':'gpt-6.1-sol','expected_effort':'medium'}
    return config,path,taskmeta


def originals(config,*,model='gpt-6.1-sol'):
    stage=Path(config['staged_root']);run=stage/'run';run.mkdir()
    spec=native.read(stage/'spec.json');put(run/'assignment.json',spec)
    put(run/'result.json',{'native_application':'JiuWenSwarm','status':'completed','model_calls':1,'selected_tool_calls':0})
    packet={'messages':[{'role':'user','content':'public task'}],'tools':[]}
    ident='a'*32
    response={'request_id':ident,'status':'completed','identity':{'effective':model,'basis':'offline observed fixture'},'reasoning_effort':'medium',
              'usage':{'input_tokens':100,'output_tokens':20}}
    put(run/'evidence/completion-0001-request.json',packet);put(run/'evidence/completion-0001-response.json',response)
    put(stage/'broker'/(ident+'.request.json'),{'request_id':ident,'model':'gpt-6.1-sol','reasoning_effort':'medium',
        'prompt':'native wire wrapper\n'+json.dumps(packet,separators=(',',':'))})
    put(stage/'broker'/(ident+'.response.json'),response)
    put(run/'project/evaluation_verdict.json',{'id':'evaluation_verdict','classification':'INCONCLUSIVE'})


def dispatch_record(config):
    return {'status':'observer_returned','task_sha256':config['task_sha256']}


def test_host_controls_and_task_are_immutable(tmp_path):
    config,path,_=fixture(tmp_path);assert native.load_host_config(path)['command']==config['command']
    (Path(config['staged_root'])/'spec.json').write_text('{}')
    with pytest.raises(ValueError,match='Pinned native control changed'):native.load_host_config(path)


@pytest.mark.asyncio
async def test_actual_native_wrapper_dispatched_only_once(tmp_path):
    config,_,_=fixture(tmp_path);calls=[]
    class Process:
        returncode=0
        async def wait(self):return 0
    async def launcher(*argv,**kwargs):
        calls.append(argv);originals(config);return Process()
    folder,receipt,cancelled=await native.dispatch(config,'offline-trial',launcher=launcher)
    assert len(calls)==1 and list(calls[0])==config['command']
    assert receipt['status']=='observer_returned' and cancelled is None
    assert (folder/'run/result.json').is_file()
    with pytest.raises(FileExistsError):await native.dispatch(config,'retry-refused',launcher=launcher)
    assert len(calls)==1


def test_original_wire_identity_and_usage_are_joined(tmp_path):
    config,_,meta=fixture(tmp_path);originals(config)
    export=native.export_originals(config,dispatch_record(config));joined=native.joined_native_evidence(export,meta)
    assert joined['identity_verified'] is True and joined['model_calls']==1
    assert joined['usage']=={'input_tokens':100,'output_tokens':20,'cached_input_tokens':None}


def test_wrong_effective_model_never_scores(tmp_path):
    config,_,meta=fixture(tmp_path);originals(config,model='wrong-model')
    export=native.export_originals(config,dispatch_record(config))
    with pytest.raises(ValueError,match='wire/model/effort'):native.joined_native_evidence(export,meta)


def test_modified_original_never_scores(tmp_path):
    config,_,meta=fixture(tmp_path);originals(config)
    export=native.export_originals(config,dispatch_record(config))
    (export/'run/result.json').write_text('{}')
    with pytest.raises(ValueError,match='inventory mismatch'):native.joined_native_evidence(export,meta)


def test_grade_requires_join_before_content_oracle(tmp_path):
    config,_,meta=fixture(tmp_path);originals(config)
    export=native.export_originals(config,dispatch_record(config));tests=tmp_path/'tests';tests.mkdir()
    put(tests/'task.json',meta);put(tests/'criteria.json',{})
    (tests/'oracle.py').write_text('def evaluate(evidence,criteria):\n return {"checks":[{"id":"literal","status":"pass","reason":"offline oracle fixture","evidence_refs":[]}],"metrics":{},"critical_violations":[]}\n')
    result=native.grade(export,tests,tmp_path/'grade')
    assert result['identity_verified'] is True and result['content_correct'] is True
    assert native.read(tmp_path/'grade/reward.json')['case_correctness']==1
    assert result['usable_completion'] is True


def test_correct_partial_content_does_not_claim_usable_completion(tmp_path):
    config,_,meta=fixture(tmp_path);originals(config)
    result_path=Path(config['staged_root'])/'run/result.json'
    value=native.read(result_path);value['status']='model_call_limit';put(result_path,value)
    export=native.export_originals(config,dispatch_record(config));tests=tmp_path/'tests';tests.mkdir()
    put(tests/'task.json',meta);put(tests/'criteria.json',{})
    (tests/'oracle.py').write_text('def evaluate(evidence,criteria):\n return {"checks":[{"status":"pass"}],"metrics":{},"critical_violations":[]}\n')
    report=native.grade(export,tests,tmp_path/'grade')
    assert report['content_correct'] is True and report['usable_completion'] is False
    assert native.read(tmp_path/'grade/reward.json')['usable_completion']==0


def test_private_auth_storage_is_not_exported(tmp_path):
    config,_,_=fixture(tmp_path);originals(config)
    put(Path(config['staged_root'])/'run/state/.codex/auth.json',{'offline':'not a real credential'})
    with pytest.raises(ValueError,match='Authentication storage'):native.export_originals(config,dispatch_record(config))


def test_prepare_freezes_real_native_agent_not_toolfree_adapter(tmp_path):
    config,_,_=fixture(tmp_path);case=tmp_path/'case';put(case/'referee/criteria.json',{})
    (case/'oracle.py').write_text('def evaluate(e,c): return {}')
    task=native.prepare_task(tmp_path/'bundle',config['staged_root'],case,python_image='python:3.12-slim@sha256:'+'a'*64)
    job=native.read(tmp_path/'bundle/job.json')
    assert job['agents'][0]['import_path']==native.ADAPTER
    assert (task/'tests/value_native_harbor.py').is_file()
    assert 'separate' in (task/'task.toml').read_text()
