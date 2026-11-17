"""Native CPU composition and explicit lifecycle fixtures; no hardware jobs."""
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.software_factory.cc_catalog import describe_capabilities
from jiuwenswarm.software_factory.cc_service import CCService
from jiuwenswarm.software_factory.cc_workflow import CCWorkflow, WorkflowConflict, digest
from jiuwenswarm.software_factory.interconnect import VERSION, select
from jiuwenswarm.software_factory.workflow_definitions import (
    Binding, StageRef, SubworkflowRef, SubworkflowDefinition, WorkflowDefinition, WorkflowRegistry,
)


def finish(runtime, run_id):
    for _ in range(12):
        result = runtime.tick(run_id)
        if result['status'] in {'completed', 'failed'}:
            return result
    raise AssertionError('CPU fixture did not settle')


@pytest.fixture
def connected(tmp_path):
    """A native fixture exposes a deferred result and a schema-bound consumer."""
    package = tmp_path / 'package'
    package.mkdir()
    (package / 'run.py').write_text('''import json,sys
p=json.load(sys.stdin);cap=p['capability'];i=p['inputs']
if cap=='submit': out={'attempt_id':'cpu-attempt','state':'running'}
elif cap in ('status','cancel'): out={'attempt_id':'cpu-attempt','task_id':'cpu-test','state':'succeeded','cleanup_state':'no_container_created'}
elif cap=='compare': out={'accepted':i['request']}
elif cap=='result': out={'attempt_id':'cpu-attempt','state':'succeeded','record':{'image':{'id':'sha256:abc'},'wrong':3}}
else: out={'accepted':i['image']}
print(json.dumps({'outcome':'ok','outputs':out}))
''')
    (package / 'cc.yaml').write_text(yaml.safe_dump(dict(cc='2', id='factory.builder', version='1.0.0',
        bindings={'default': {'kind': 'native', 'command': ['{python}', '{bundle}/run.py']}}, capabilities={
        'submit': dict(does='CPU lifecycle fixture', takes={'request':'json','idem_key':'text'}, gives={'attempt_id':'text','state':'text'}),
        'status': dict(does='CPU status fixture', takes={'attempt_id':'text'}, gives={'attempt_id':'text','task_id':'text','state':'text','cleanup_state':'text'}),
        'cancel': dict(does='CPU cancel fixture', takes={'attempt_id':'text'}, gives={'attempt_id':'text','task_id':'text','state':'text','cleanup_state':'text'}),
        'result': dict(does='CPU result fixture', takes={'attempt_id':'text'}, gives={'attempt_id':'text','state':'text','record':'json'}),
        'compare': dict(does='Validate a CPU comparison request', takes={'request':{'kind':'json','schema':{'type':'object','required':['stage','build_attempt_id'],'additionalProperties':False,'properties':{'stage':{'const':'screen'},'build_attempt_id':{'const':'cpu-attempt'}}}}}, gives={'accepted':'json'}),
        'consume': dict(does='Consume a completed image identity', takes={'image':{'kind':'text','schema':{'type':'string','pattern':'^sha256:'}}}, gives={'accepted':'text'})})))
    host = Host(tmp_path / 'host', session_grants=[])
    caps = describe_capabilities(host, [host.seal(package)])
    source = SubworkflowDefinition('produce', 'Produce', {'request':'json'}, (
        StageRef('job','factory.builder:submit',{'request':Binding('$input','request')}),),
        {'image': Binding('job','record',channel='result',pointer='/image/id',kind='text')})
    sink = SubworkflowDefinition('consume', 'Consume', {'image':'text'}, (
        StageRef('use','factory.builder:consume',{'image':Binding('$input','image')}),), {'accepted':Binding('use','accepted')})
    flow = WorkflowDefinition('connected','Connected',{'request':'json'}, (
        SubworkflowRef('producer','produce',{'request':Binding('$input','request')}),
        SubworkflowRef('consumer','consume',{'image':Binding('producer','image')})), {'accepted':Binding('consumer','accepted')})
    registry = WorkflowRegistry(caps,[source,sink],[flow])
    runtime = CCWorkflow(tmp_path / 'runs',host,caps,task_id='cpu-test',interconnect=VERSION)
    return runtime, registry, host, caps


def test_completed_result_crosses_subworkflow_boundary_and_restart(connected):
    runtime, registry, host, caps = connected
    run = runtime.create(registry.expand('connected'),{'request':{}},objective='Connect native CPU components')
    first = runtime.tick(run['id'])
    assert first['nodes'][0]['state']=='waiting'
    assert first['nodes'][1]['state']=='pending'
    restarted = CCWorkflow(runtime.root,host,caps,task_id='cpu-test',interconnect=VERSION)
    done = finish(restarted,run['id'])
    assert done['outputs']=={'accepted':'sha256:abc'}
    assert done['nodes'][0]['outputs']=={'attempt_id':'cpu-attempt','state':'running'}
    assert done['nodes'][0]['completion_outputs']['record']['image']['id']=='sha256:abc'
    binding = done['nodes'][1]['inputs']['image']
    assert binding['channel']=='result' and binding['pointer']=='/image/id'
    assert all(node['receipts'] for node in done['nodes'])
    assert done['acceptance']=='not_assessed'
    assert runtime.events(run['id'])[-2]['completion_outputs']=={}
    assert CCService(runtime,registry).catalog()['capabilities'][0]['input_contracts']


@pytest.mark.parametrize('pointer,kind', [('/missing','text'),('/wrong','text'),('/image/id','json')])
def test_bad_connection_never_invokes_consumer(connected,pointer,kind):
    runtime, registry, host, caps = connected
    graph = registry.expand('connected')
    consumer = graph.nodes[1]
    ref = consumer.input_bindings['image']
    altered = replace(ref,pointer=pointer,kind=kind)
    graph = replace(graph,nodes=(graph.nodes[0],replace(consumer,input_bindings={'image':altered})))
    if kind=='json':
        with pytest.raises(ValueError):
            runtime.create(graph,{'request':{}},objective='Reject mismatched port kind')
    else:
        done=finish(runtime,runtime.create(graph,{'request':{}},objective='Reject bad producer value')['id'])
        assert done['status']=='failed'
        assert done['nodes'][1]['error']=='interconnect_contract_mismatch'
        assert not done['nodes'][1]['receipts']
    with host.db() as db:
        assert all(json.loads(row[0])['capability']!='consume' for row in db.execute('SELECT receipt FROM calls'))


def test_destination_schema_rejects_shape_compatible_text(connected):
    runtime, registry, host, caps = connected
    graph = registry.expand('connected/consumer')
    with pytest.raises(ValueError):
        runtime.create(graph,{'image':'unidentified-image'},objective='Reject invalid image identity')
    with host.db() as db:
        assert db.execute('SELECT count(*) FROM calls').fetchone()[0]==0


def test_legacy_identity_and_version_gate(connected,tmp_path):
    runtime, registry, host, caps = connected
    legacy=CCWorkflow(tmp_path/'legacy',host,caps,task_id='cpu-test')
    expected=digest(dict(task='cpu-test',grants=[],context={},host=str(host.store),
                        capabilities=[c.serializable() for c in caps],max_nodes=128,deadline=None))
    assert legacy.identity==expected
    with pytest.raises(ValueError,match='Extended bindings'):
        legacy.create(registry.expand('connected'),{'request':{}},objective='Require version opt-in')
    with pytest.raises(ValueError,match='Unsupported interconnect'):
        CCWorkflow(tmp_path/'unknown',host,caps,task_id='cpu-test',interconnect='factory.interconnect/99')


@pytest.mark.parametrize('pointer', ['image/id','/~2bad','/array/-','/array/01','/array/8'])
def test_bad_json_pointers_are_rejected(pointer):
    with pytest.raises(ValueError):
        select({'array':[1]},pointer)


def test_pointer_escaping_and_schema_agree():
    assert select({'a/b':{'~':[7]}},'/a~1b/~0/0')==7
    schema=json.loads((Path(__file__).parents[2]/'jiuwenswarm/software_factory/interconnect.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    validator=Draft202012Validator(schema)
    validator.validate(asdict(Binding('job','record',channel='result',pointer='/image/id',kind='text')))
    with pytest.raises(ValidationError):
        validator.validate({'source':'job','port':'record','pointer':'/image'})
    with pytest.raises(ValueError):
        Binding('job','record',pointer='/image')


def test_build_identity_assembles_a_valid_comparison_request(connected):
    runtime, registry, host, caps = connected
    source = registry.subworkflows['produce']
    source = replace(source, outputs={'build_id': Binding('job','attempt_id',channel='result')})
    sink = SubworkflowDefinition('evaluate','Evaluate',{'request':'json'}, (
        StageRef('compare','factory.builder:compare',{'request':Binding('$input','request')}),),
        {'accepted':Binding('compare','accepted')})
    assembly = {'template':{'stage':'screen'},'at':'/build_attempt_id'}
    flow = WorkflowDefinition('candidate','Candidate',{'request':'json'}, (
        SubworkflowRef('build','produce',{'request':Binding('$input','request')}),
        SubworkflowRef('evaluate','evaluate',{'request':Binding('build','build_id',assemble=assembly)})),
        {'accepted':Binding('evaluate','accepted')})
    registry = WorkflowRegistry(caps,[source,sink],[flow])
    done = finish(runtime,runtime.create(registry.expand('candidate'),{'request':{}},objective='Connect build to comparison')['id'])
    assert done['outputs']['accepted']=={'stage':'screen','build_attempt_id':'cpu-attempt'}
    assert assembly['template']=={'stage':'screen'}
    assert done['nodes'][1]['inputs']['request']['assemble']==assembly


def test_failed_output_projection_is_a_recorded_failure(connected):
    runtime, registry, host, caps = connected
    graph = registry.expand('connected')
    bad = replace(graph.nodes[1].input_bindings['image'],pointer='/missing')
    graph = replace(graph,outputs={'missing':bad})
    done = finish(runtime,runtime.create(graph,{'request':{}},objective='Reject missing exported result')['id'])
    assert done['status']=='failed'
    assert done['output_error']=='interconnect_contract_mismatch'


def test_new_preparations_use_the_versioned_contract(connected,tmp_path):
    from jiuwenswarm.software_factory.cc_prepare import prepare
    # Use a non-factory package id so service creation has no live task dependency.
    package=tmp_path/'package'
    manifest=yaml.safe_load((package/'cc.yaml').read_text())
    manifest['id']='test.component'
    manifest['capabilities']={'consume':manifest['capabilities']['consume']}
    (package/'cc.yaml').write_text(yaml.safe_dump(manifest))
    config=tmp_path/'prepared/config.json'
    prepare(config,'cpu-test',[package])
    service=CCService.from_config(config)
    assert service.catalog()['interconnect']==VERSION
    assert service.catalog()['interconnect_schema']['$id']=='urn:factory:interconnect:1'
    assert service.catalog()['capabilities'][0]['input_contracts']['image']['schema']['pattern']=='^sha256:'
