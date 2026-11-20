"""Real-file evidence custody tests; fixture graphs are not Agent-run evidence."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from fastapi import FastAPI
import httpx
import pytest

from jiuwenswarm.software_factory import library_api
from jiuwenswarm.software_factory.library_evidence import (
    ComponentChecks, EvidenceConflict, import_materials, import_material, _canonical_version,
    model_attempt_projection, publish_model_attempt, latest_model_attempt,
)
from jiuwenswarm.software_factory.model_driver import execute_process
from jiuwenswarm.software_factory.workflow_library import WorkflowLibrary, write_json


PREFIX='/api/v1/factory/library'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class Client:
    def __init__(self,app):self.app=app
    def get(self,path,**kwargs):
        async def request():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://testserver') as client:
                return await client.get(path,**kwargs)
        return asyncio.run(request())


@pytest.fixture
def component(tmp_path):
    factory=tmp_path/'factory';library_root=factory/'workflow-library'
    directory=factory/'checks'/'isolated-check'
    project=directory/'nodes'/'generate'/'project'
    cpp=project/'src'/'ascend'/'router.cpp'
    cpp.parent.mkdir(parents=True)
    cpp.write_text('// Isolated custody fixture, not a migration.\nint test_source() { return 1; }\n')
    manifest=directory/'nodes'/'generate'/'project-manifest.json'
    write_json(manifest,{'schema':'factory.source-project.v1','source_dir':str(project),
                         'files':{'src/ascend/router.cpp':sha(cpp)}})
    definition=WorkflowLibrary(library_root).register({'id':'fixture_source','name':'Isolated source fixture',
        'source':{'repository':'test-only','checkout':str(project)},'subworkflows':[
            {'id':'generate','name':'Fixture metadata','inputs':{},'outputs':{'project':{'semantic_type':'source.project'}},
             'implementation':{'type':'python','entrypoint':'jiuwenswarm.software_factory.library_operations:report'}}]})
    artifact={'id':'isolated-check:generate:1:project','kind':'source.project','path':str(manifest),
              'sha256':sha(manifest),'size':manifest.stat().st_size,'producer':'generate','port':'project'}
    graph={'selection_source':'explicit_component_check_not_agent_plan','nodes':[
        {'id':'generate','workflow':{key:definition[key] for key in ('id','version')},'subworkflow':'generate'}]}
    events=[{'sequence':1,'type':'graph.validated','payload':{'graph':graph}},
            {'sequence':2,'type':'artifact.published','payload':{'artifact':artifact}},
            {'sequence':3,'type':'run.verified','payload':{'test_fixture':True}}]
    run={'id':directory.name,'status':'verified','created_at':'2026-11-19T00:00:00+00:00',
         'run_dir':str(directory),'graph':graph,'nodes':[],'artifacts':[artifact],
         'sequence':len(events),'test_fixture':True}
    write_json(directory/'run.json',run);write_json(directory/'graph.json',graph)
    (directory/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    command=execute_process([sys.executable,'-c','print("isolated real evidence-test process")'],factory,
                            factory/'checks'/'verification-commands'/'1')
    report={'selection_source':graph['selection_source'],'run_dir':str(directory),'status':'verified',
            'commands':[command],'agent_planning_validated':False,'native_device_validated':False,
            'full_inference_validated':False,'test_fixture':True}
    write_json(factory/'checks'/'fixture-verification.json',report)
    return {'factory':factory,'library_root':library_root,'directory':directory,'run':run,'events':events,
            'artifact':artifact,'cpp':cpp,'manifest':manifest,'command':command,'report':report}


def test_original_run_and_events_are_not_rewritten_or_merged_with_post_run_commands(component):
    store=ComponentChecks(component['factory'],component['library_root'])
    value=store.get(component['directory'].name,'local-operator')
    assert value['run']==component['run']
    assert value['events']==component['events']
    assert value['verification']==component['report']
    assert value['command_records']==[component['command']]
    assert value['recording_provenance']['post_run_verification_is_separate'] is True
    assert value['selection_source']=='explicit_component_check_not_agent_plan'
    assert value['read_only'] is True
    assert value['workflow_definitions'][0]['id']=='fixture_source'
    assert value['verification']['agent_planning_validated'] is False
    assert store.list('another-account')==[]
    with pytest.raises(FileNotFoundError):store.get(component['directory'].name,'another-account')


def test_download_only_original_published_artifacts_and_exact_member_hashes(component):
    store=ComponentChecks(component['factory'],component['library_root'])
    identity=component['directory'].name;artifact_id=component['artifact']['id']
    path,artifact=store.artifact(identity,artifact_id,'local-operator')
    assert path==component['manifest']
    member,digest=store.project_file(identity,artifact_id,'src/ascend/router.cpp','local-operator')
    assert member==component['cpp'] and digest==sha(member)
    with pytest.raises(FileNotFoundError):store.project_file(identity,artifact_id,'../../run.json','local-operator')
    component['cpp'].write_text('changed after publication\n')
    with pytest.raises(EvidenceConflict,match='changed'):
        store.project_file(identity,artifact_id,'src/ascend/router.cpp','local-operator')


def test_changed_independent_command_and_incomplete_event_sequence_fail_closed(component):
    store=ComponentChecks(component['factory'],component['library_root'])
    stderr=Path(component['command']['stderr_path'])
    stderr.write_text('not the actual recorded stderr\n')
    with pytest.raises(EvidenceConflict,match='output changed'):
        store.get(component['directory'].name,'local-operator')
    stderr.write_text(component['command']['stderr'])
    event_path=component['directory']/'events.jsonl'
    event_path.write_text(json.dumps(component['events'][0])+'\n')
    with pytest.raises(EvidenceConflict,match='sequence'):
        store.get(component['directory'].name,'local-operator')


def test_evidence_root_symlinks_and_artifact_escape_are_rejected(component,tmp_path):
    store=ComponentChecks(component['factory'],component['library_root'])
    (component['directory']/'alias').symlink_to(tmp_path)
    with pytest.raises(FileNotFoundError):store.get('../outside','local-operator')
    run=deepcopy(component['run'])
    outside=tmp_path/'private.txt';outside.write_text('unrelated file')
    run['artifacts'][0].update(path=str(outside),sha256=sha(outside),size=outside.stat().st_size)
    write_json(component['directory']/'run.json',run)
    events=deepcopy(component['events']);events[1]['payload']['artifact']=run['artifacts'][0]
    (component['directory']/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    with pytest.raises(EvidenceConflict,match='outside'):
        store.artifact(component['directory'].name,run['artifacts'][0]['id'],'local-operator')


def test_http_routes_are_read_only_owned_and_exact_file_downloads(component,monkeypatch):
    service=library_api.LibraryService(component['library_root'])
    monkeypatch.setattr(library_api,'LibraryService',lambda root:service)
    async def owner(request,action='status'):
        assert action=='status'
        return request.headers.get('x-test-owner','local-operator')
    app=FastAPI();app.include_router(library_api.create_library_router(service.root,owner),prefix='/api/v1/factory')
    client=Client(app)
    try:
        assert client.get(PREFIX+'/checks').json()['checks'][0]['id']==component['directory'].name
        assert client.get(PREFIX+'/checks',headers={'x-test-owner':'bob'}).json()['checks']==[]
        base=PREFIX+'/checks/'+component['directory'].name
        detail=client.get(base)
        assert detail.status_code==200 and detail.json()['run']==component['run']
        assert client.get(base,headers={'x-test-owner':'bob'}).status_code==404
        url=base+'/artifacts/'+component['artifact']['id']
        assert client.get(url).content==component['manifest'].read_bytes()
        member=client.get(url+'/file',params={'path':'src/ascend/router.cpp'})
        assert member.status_code==200 and member.content==component['cpp'].read_bytes()
        assert member.headers['x-content-sha256']==sha(component['cpp'])
        assert client.get(url+'/file',params={'path':'../run.json'}).status_code==404
    finally:service.pool.shutdown(wait=True)


def test_owned_import_history_survives_reload_and_materials_are_confined(tmp_path,monkeypatch):
    service=library_api.LibraryService(tmp_path/'factory'/'workflow-library')
    monkeypatch.setattr(library_api,'LibraryService',lambda root:service)
    async def owner(request,action='status'):return request.headers.get('x-test-owner','alice')
    app=FastAPI();app.include_router(library_api.create_library_router(service.root,owner),prefix='/api/v1/factory')
    client=Client(app)
    identity='a'*32;directory=service.directory('imports',identity)
    write_json(directory/'job.json',{'id':identity,'owner_id':'alice','kind':'imports','status':'completed',
        'created_at':'2026-11-19T00:00:00+00:00','request':{'repository_url':'test-only'},'test_fixture':True})
    service.emit('imports',identity,'job.finished',{'status':'completed','test_fixture':True})
    try:
        history=client.get(PREFIX+'/imports').json()['jobs']
        assert history[0]['id']==identity
        assert history[0]['events'][0]['type']=='job.finished'
        assert history[0]['materials']==[]
        assert client.get(PREFIX+'/imports',headers={'x-test-owner':'bob'}).json()['jobs']==[]
        assert client.get(PREFIX+'/imports/'+identity,headers={'x-test-owner':'bob'}).status_code==404
        assert client.get(PREFIX+'/imports/'+identity+'/materials/unknown').status_code==404
    finally:service.pool.shutdown(wait=True)


@pytest.mark.parametrize('current_format',[False,True])
def test_import_wrapper_files_and_registered_definition_are_bound_to_the_record(tmp_path,current_format):
    """Isolated import-material custody fixture, without network/source claims."""
    library=WorkflowLibrary(tmp_path/'workflow-library')
    identity='a'*32
    receipt=library.root/'projects'/identity/'imports'/'fixture'
    wrapper=receipt/'wrappers'/'report'
    wrapper.mkdir(parents=True)
    decomposition=receipt/'source-decomposition.json'
    write_json(decomposition,{'test_fixture':True,'source_components':[]})
    part={'id':'report','name':'Isolated report wrapper','inputs':{},
          'outputs':{'report':{'semantic_type':'analysis.report'}},
          'implementation':{'type':'python','entrypoint':'jiuwenswarm.software_factory.library_operations:report'}}
    if not current_format:write_json(wrapper/'workflow.json',part)
    (wrapper/'execute.py').write_text('from jiuwenswarm.software_factory.library_operations import report as execute\n')
    part['wrapper_manifest']=str(wrapper/'workflow.json')
    if current_format:
        part['inspection']={'wrapper':{'manifest':part['wrapper_manifest'],
                                      'entry':str(wrapper/'execute.py'),'sha256':sha(wrapper/'execute.py')}}
        write_json(wrapper/'workflow.json',part)
    source={'repository':'test-only','decomposition_path':str(decomposition),
            'decomposition_sha256':sha(decomposition)}
    bundle={'id':'fixture','name':'Isolated material fixture','source':source,'subworkflows':[part]}
    if current_format:
        from jiuwenswarm.software_factory.workflow_imports import validate_composition
        composition=validate_composition([part],{'inputs':{},'nodes':[
            {'id':'report','part':'report','bindings':{}}],
            'outputs':{'report':{'node':'report','port':'report'}}})
        composition_path=receipt/'parent-composition.json'
        write_json(composition_path,composition)
        bundle.update(composition=composition,composition_manifest=str(composition_path),
                      composition_sha256=sha(composition_path),default_flow_role='display_only')
    bundle['version']=_canonical_version(bundle)
    write_json(receipt/'workflow-bundle.json',bundle)
    write_json(receipt/'acquisition.json',{'test_fixture':True,'commands':[]})
    registered=library.register(bundle)
    job={'id':identity,'owner_id':'alice','workflow':registered,'test_fixture':True}
    materials=import_materials(library.root,job)
    expected={
        'source-decomposition','acquisition','workflow-bundle','registered-workflow',
        'part.report.definition','part.report.entrypoint'}
    if current_format:expected.add('parent-composition')
    assert {row['id'] for row in materials}==expected
    read=import_material(library.root,job,'part.report.entrypoint')
    assert read['content']==(wrapper/'execute.py').read_text()
    assert read['integrity']==('recorded-sha256' if current_format else 'observed-bytes')
    definition=import_material(library.root,job,'registered-workflow')
    assert json.loads(definition['content'])==registered
    with pytest.raises(FileNotFoundError):import_material(library.root,job,'../../private.txt')
    if current_format:
        entry=wrapper/'execute.py';original=entry.read_bytes()
        entry.write_text('changed wrapper\n')
        with pytest.raises(EvidenceConflict,match='bytes changed'):import_materials(library.root,job)
        entry.write_bytes(original)
        original=composition_path.read_bytes();composition_path.write_text('{"changed":true}\n')
        with pytest.raises(EvidenceConflict,match='bytes changed'):import_materials(library.root,job)
        composition_path.write_bytes(original)
    decomposition.write_text('{"changed":"after import"}\n')
    with pytest.raises(EvidenceConflict,match='bytes changed'):
        import_materials(library.root,job)


def test_model_attempt_projection_uses_recorded_values_and_never_serves_raw_text(tmp_path):
    """Isolated receipt fixtures test projection; no live model is invoked."""
    root=tmp_path/'factory'
    first=tmp_path/'first'/'invocation.json'
    write_json(first,{'exit_code':2,'finished_at':'2026-11-19T12:00:00+00:00','driver':'codex-cli',
        'model':'configured-default','stderr':'HTTP status 503 Service Unavailable sk-PRIVATE_TEST_SECRET',
        'stdout':json.dumps({'type':'turn.failed','error':{'message':'Service unavailable'}})})
    projected=model_attempt_projection(first)
    assert projected['observed_http_statuses']==[503]
    assert projected['reason_code']=='process_failed' and projected['outcome']=='failed'
    publish_model_attempt(first,root)
    second=tmp_path/'second'/'invocation.json'
    write_json(second,{'exit_code':1,'finished_at':'2026-11-19T13:00:00+00:00','driver':'codex-cli',
        'model':'configured-default','stderr':'response: 401 Unauthorized api_key=PRIVATE_TEST_KEY',
        'stdout':json.dumps({'type':'turn.failed','error':{'message':'Your access token could not be refreshed'}})})
    publish_model_attempt(second,root)
    latest=latest_model_attempt(root,'local-operator')
    assert latest['observed_http_statuses']==[401]
    assert latest['reason_code']=='authentication_failed'
    assert latest['recorded_at']=='2026-11-19T13:00:00+00:00'
    assert latest['live_probe'] is False and latest['evidence_kind']=='recorded_invocation'
    assert 'PRIVATE_TEST' not in json.dumps(latest)
    assert not {'stdout','stderr','source_receipt_path','prompt_path'} & set(latest)
    assert latest_model_attempt(root,'another-account') is None
    second.write_text('{"changed":"after projection"}\n')
    assert latest_model_attempt(root,'local-operator')['observed_http_statuses']==[503]


def test_model_attempt_http_boundary_exposes_only_local_recorded_projection(tmp_path,monkeypatch):
    service=library_api.LibraryService(tmp_path/'factory'/'workflow-library')
    monkeypatch.setattr(library_api,'LibraryService',lambda root:service)
    async def owner(request,action='status'):return request.headers.get('x-test-owner','local-operator')
    app=FastAPI();app.include_router(library_api.create_library_router(service.root,owner),prefix='/api/v1/factory')
    client=Client(app)
    try:
        assert client.get(PREFIX+'/model-connection').json()=={'attempt':None}
        receipt=tmp_path/'recorded'/'invocation.json'
        write_json(receipt,{'exit_code':1,'driver':'codex-cli','model':'configured-default',
            'finished_at':'2026-11-19T13:00:00+00:00','stderr':'HTTP status 403 Forbidden',
            'stdout':json.dumps({'type':'error','message':'Authentication failed'})})
        publish_model_attempt(receipt,service.root.parent)
        response=client.get(PREFIX+'/model-connection')
        assert response.status_code==200
        assert response.json()['attempt']['observed_http_statuses']==[403]
        assert response.json()['attempt']['reason_code']=='authentication_failed'
        assert client.get(PREFIX+'/model-connection',headers={'x-test-owner':'bob'}).json()=={'attempt':None}
        assert 'source_receipt_path' not in response.text
    finally:service.pool.shutdown(wait=True)
